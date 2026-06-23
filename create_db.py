"""The same as running `python generate_data.py` (which also rebuilds),
provided as a separate entry point .

Run:  python create_db.py
"""

from generate_data import main as generate

if __name__ == "__main__":
    generate()
    print("\nDatabase saved as maintenance.db")
    print("To start app host: run python app.py")
