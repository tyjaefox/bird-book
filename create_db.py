"""One-shot setup: build the schema and populate synthetic data.

Equivalent to running `python generate_data.py` (which also rebuilds the schema),
provided as a separate entrypoint for clarity.

Run:  python create_db.py
"""

from generate_data import main as generate

if __name__ == "__main__":
    generate()
    print("\nDatabase ready -> maintenance.db")
    print("Start the app with:  python app.py")
