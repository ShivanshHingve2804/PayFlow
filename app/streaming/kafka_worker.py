"""Post-commit transactional outbox relay and idempotent Kafka consumer."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import OutboxEvent, ProcessedEvent

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    """Minimal publisher interface allowing Kafka or test-double injection."""

    def publish(self, topic: str, key: str, value: bytes) -> None: ...


class KafkaEventPublisher:
    """Idempotent Kafka producer (`acks=all`, `enable.idempotence=True`)."""

    def __init__(self, bootstrap_servers: str) -> None:
        from confluent_kafka import Producer

        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "acks": "all",
                "enable.idempotence": True,
                "retries": 5,
            }
        )

    def publish(self, topic: str, key: str, value: bytes) -> None:
        delivery_errors: list[BaseException] = []

        def _on_delivery(err: Any, _msg: Any) -> None:
            if err is not None:
                delivery_errors.append(RuntimeError(str(err)))

        self._producer.produce(
            topic=topic,
            key=key.encode("utf-8"),
            value=value,
            on_delivery=_on_delivery,
        )
        remaining = self._producer.flush(timeout=10.0)
        if remaining > 0:
            raise TimeoutError(f"Kafka flush timed out with {remaining} message(s)")
        if delivery_errors:
            raise delivery_errors[0]


class OutboxRelay:
    """Publishes committed `outbox_events` rows to Kafka without dual-write races."""

    @staticmethod
    def build_envelope(event: OutboxEvent) -> dict[str, Any]:
        return {
            "event_id": event.id,
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "payload": json.loads(event.payload),
            "created_at": event.created_at.isoformat(),
        }

    @staticmethod
    def publish_pending_batch(
        db: Session,
        publisher: EventPublisher,
        *,
        topic: str | None = None,
        batch_size: int | None = None,
    ) -> int:
        target_topic = topic or settings.KAFKA_TOPIC_TRANSACTIONS
        limit = batch_size or settings.OUTBOX_BATCH_SIZE

        bind = db.get_bind()
        supports_skip_locked = bind is not None and bind.dialect.name != "sqlite"

        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == "PENDING")
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        )
        if supports_skip_locked:
            stmt = stmt.with_for_update(skip_locked=True)

        pending = list(db.execute(stmt).scalars().all())
        if not pending:
            return 0

        published_count = 0
        now = datetime.now(timezone.utc)
        for event in pending:
            envelope = OutboxRelay.build_envelope(event)
            encoded = json.dumps(envelope, sort_keys=True).encode("utf-8")
            publisher.publish(target_topic, event.aggregate_id, encoded)
            event.status = "PUBLISHED"
            event.published_at = now
            published_count += 1

        db.commit()
        return published_count


class AuditEventConsumer:
    """Consumes transaction events and deduplicates replays via `processed_events`."""

    @staticmethod
    def process_event(
        db: Session,
        event: dict[str, Any],
        *,
        consumer_group: str | None = None,
    ) -> bool:
        """Process an event idempotently. Returns `True` if new, `False` if duplicate."""
        event_id = str(event["event_id"])
        event_type = str(event["event_type"])
        group = consumer_group or settings.KAFKA_GROUP_ID

        record = ProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            consumer_group=group,
        )
        db.add(record)
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            logger.info("Deduplicated duplicate Kafka event_id=%s", event_id)
            return False


def run_relay_loop(poll_interval: float = 1.0) -> None:
    publisher = KafkaEventPublisher(settings.KAFKA_BOOTSTRAP_SERVERS)
    logger.info(
        "Outbox relay started (bootstrap=%s, topic=%s)",
        settings.KAFKA_BOOTSTRAP_SERVERS,
        settings.KAFKA_TOPIC_TRANSACTIONS,
    )
    while True:
        db = SessionLocal()
        try:
            count = OutboxRelay.publish_pending_batch(db, publisher)
            if count:
                logger.info("Published %d outbox event(s) to Kafka", count)
        except Exception as exc:
            db.rollback()
            logger.warning("Outbox relay iteration failed: %s", exc)
        finally:
            db.close()
        time.sleep(poll_interval)


def run_consumer_loop() -> None:
    from confluent_kafka import Consumer

    consumer = Consumer(
        {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": settings.KAFKA_GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([settings.KAFKA_TOPIC_TRANSACTIONS])
    logger.info(
        "Kafka deduplicating consumer started (topic=%s, group=%s)",
        settings.KAFKA_TOPIC_TRANSACTIONS,
        settings.KAFKA_GROUP_ID,
    )
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                logger.warning("Kafka consumer error: %s", msg.error())
                continue
            raw_value = msg.value()
            if raw_value is None:
                continue
            payload = json.loads(raw_value.decode("utf-8"))
            db = SessionLocal()
            try:
                AuditEventConsumer.process_event(db, payload)
                consumer.commit(message=msg, asynchronous=False)
            finally:
                db.close()
    finally:
        consumer.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="PayFlow Kafka Streaming Workers")
    parser.add_argument("role", choices=["relay", "consumer"])
    args = parser.parse_args()
    if args.role == "relay":
        run_relay_loop()
    else:
        run_consumer_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
