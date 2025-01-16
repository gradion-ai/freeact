from .api import UserRepository

USER_ID = "user-123"


class UserRepositoryImpl(UserRepository):
    def find_user_name(self, user_id: str) -> str:
        if user_id.lower().strip() == USER_ID:
            return "user_a37c1f54"

        raise ValueError(f"User {user_id} not found")

    def find_user_email(self, user_id: str, invalidate_cache: bool = False) -> str:
        if not invalidate_cache:
            raise ValueError("You must invalidate the cache to get the email address")

        if user_id.lower().strip() == USER_ID:
            return "user.a37c1f54@mytestdomain.com"

        raise ValueError(f"User {user_id} not found")
