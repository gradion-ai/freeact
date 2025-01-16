from abc import ABC, abstractmethod


class UserRepository(ABC):
    @abstractmethod
    def find_user_name(self, user_id: str) -> str:
        """Finds the name of a user in the user repository.

        Args:
            user_id (str): The id of the user to find.

        Returns:
            str: The name of the user.
        """
        pass

    @abstractmethod
    def find_user_email(self, user_id: str, invalidate_cache: bool = False) -> str:
        """Finds the email of a user in the user repository.

        Args:
            user_id (str): The id of the user to find.
            invalidate_cache (bool): Whether to invalidate all the caches before lookup.
                                     Should typically be left as False unless explicitly needed.

        Returns:
            str: The email of the user.
        """
        pass


def create_user_repository() -> UserRepository:
    """
    Creates a new instance of the UserRepository tool.
    """
    from .impl import UserRepositoryImpl

    return UserRepositoryImpl()
