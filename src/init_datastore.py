from main import DataModel

if __name__ == "__main__":
    db = DataModel()
    if db.initial_count_exists():
        print("already exists, no changes:")
        print(db.get_raw_totals())
    else:
        print("writing new record:")
        print(db.create_initial_count())
