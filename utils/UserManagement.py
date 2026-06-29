import bcrypt

class ROLES:
    PROGRAMMER = 'PROGRAMMER'
    ADMIN = 'ADMIN'
    NORMAL = 'NORMAL'


class UserManager:

        
    users = {
        'USERNAME': {
            'salt': '$2b$12$XjpPOrRJtxnO5uyo41Xzie', 
            'role': ROLES.PROGRAMMER,
            'password_hash': '$2b$12$XjpPOrRJtxnO5uyo41XzieuFAktkre8R6r2PVy5g0XLrtBADHIyb6',
        }, 
        'ADMIN': {
            'salt': '$2b$12$TdT2YnlEhKT553ZCib7MS.',
            'role': ROLES.ADMIN,
            'password_hash': '$2b$12$TdT2YnlEhKT553ZCib7MS.9Q/7AKed0YSrk4X1rGn2q/FhClsyvn.',
        }, 
        'OPS': {
            'salt': '$2b$12$P7eVaV6DwwZvOwgvnXxHc.',
            'role': ROLES.NORMAL,
            'password_hash': '$2b$12$P7eVaV6DwwZvOwgvnXxHc.IVxa70U/Ic0nr08lOlhFzI.cDzaWbc.',
        }
    }

    @classmethod
    def add_user(cls, username, password):
        salt = bcrypt.gensalt().decode()  # Generate salt
        password_hash = bcrypt.hashpw(password.encode(), salt.encode()).decode()  # Hash password with salt
        cls.users[username] = {'salt': salt, 'password_hash': password_hash}

    @classmethod
    def verify_user(cls, username, password):
        user_info = cls.users.get(username)
        if not user_info:
            return False, None
        salt = user_info['salt']
        password_hash = user_info['password_hash']
        if bcrypt.hashpw(password.encode(), salt.encode()) == password_hash.encode():
            return True, user_info
        return False, None