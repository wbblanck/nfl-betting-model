"""Build the S1 tracker dashboard page from the committed tracker files: python scripts/dashboard.py"""
from nflbet import dashboard

if __name__ == "__main__":
    print(dashboard.write())
