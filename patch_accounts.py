with open('app/services/account_service.py', 'r') as f:
    code = f.read()

new_method = '''    @staticmethod
    def list_accounts(db: Session) -> list[Account]:
        return db.query(Account).order_by(Account.created_at.desc()).all()

    @staticmethod
    def create_account'''

code = code.replace('    @staticmethod\n    def create_account', new_method)

with open('app/services/account_service.py', 'w') as f:
    f.write(code)

with open('app/routes/accounts.py', 'r') as f:
    r_code = f.read()

new_route = '''@router.get('/', response_model=list[AccountResponse])
def list_accounts(db: Session = Depends(get_db)):
    \"\"\"List all accounts.\"\"\"
    return AccountService.list_accounts(db)

@router.post('/', response_model=AccountResponse, status_code=status.HTTP_201_CREATED)'''

r_code = r_code.replace('@router.post(\'/\', response_model=AccountResponse, status_code=status.HTTP_201_CREATED)', new_route)

with open('app/routes/accounts.py', 'w') as f:
    f.write(r_code)

