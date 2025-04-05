from app import app, db, HistoryEntry
import json

def export_to_jsonl(output_file="data.jsonl"):
    with app.app_context():
        entries = HistoryEntry.query.order_by(HistoryEntry.id.asc()).all()

        with open(output_file, "w") as f:
            for entry in entries:
                input_text = f"User: {entry.text.strip()}\nContext: {entry.context or 'General'}\n"
                output_text = entry.text.strip()
                f.write(json.dumps({"input": input_text, "output": output_text}) + "\n")

        print(f"✅ Exported {len(entries)} entries to {output_file}")

if __name__ == "__main__":
    export_to_jsonl()
