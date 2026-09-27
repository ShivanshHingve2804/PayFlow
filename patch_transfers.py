with open('app/services/transfer_service.py', 'r') as f:
    code = f.read()

new_method = '''    @staticmethod
    def list_transfers(db: Session):
        from app.models import Transaction
        return db.query(Transaction).order_by(Transaction.created_at.desc()).all()

    @staticmethod
    def create_transfer'''

code = code.replace('    @staticmethod\n    def create_transfer', new_method)

with open('app/services/transfer_service.py', 'w') as f:
    f.write(code)

with open('app/routes/transfers.py', 'r') as f:
    r_code = f.read()

new_route = '''@router.get('/', response_model=list[TransferResponse])
def list_transfers(db: Session = Depends(get_db)):
    \"\"\"List all transfers.\"\"\"
    return TransferService.list_transfers(db)

@router.post('/', response_model=TransferResponse, status_code=status.HTTP_201_CREATED)'''

r_code = r_code.replace('@router.post(\'/\', response_model=TransferResponse, status_code=status.HTTP_201_CREATED)', new_route)

with open('app/routes/transfers.py', 'w') as f:
    f.write(r_code)

