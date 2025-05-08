from dotenv import load_dotenv

from freeact.cli.main import app

if __name__ == "__main__":
    load_dotenv()
    app()
