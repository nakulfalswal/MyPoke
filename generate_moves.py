import requests
import json
import time

def generate_kanto_moves():
    """
    Fetches all moves from Generation 1 (Kanto) from PokéAPI
    and generates a moves.json file with power, type, and category.
    """
    moves_dict = {}

    print("Fetching Generation 1 moves from PokéAPI...")
    print("This may take a few minutes...\n")

    # Fetch the Generation 1 move list
    gen1_response = requests.get("https://pokeapi.co/api/v2/generation/1/")
    gen1_data = gen1_response.json()

    # Get all moves from Gen 1
    gen1_moves = gen1_data["moves"]

    print(f"Found {len(gen1_moves)} Generation 1 moves!\n")

    for move_entry in gen1_moves:
        try:
            move_name = move_entry["name"]

            # Fetch detailed move data
            move_response = requests.get(move_entry["url"])
            move_data = move_response.json()

            # Get move properties
            power = move_data["power"] if move_data["power"] else 0
            move_type = move_data["type"]["name"].capitalize()

            # Determine category (physical/special/status)
            damage_class = move_data["damage_class"]["name"]
            if damage_class == "physical":
                category = "physical"
            elif damage_class == "special":
                category = "special"
            else:
                category = "status"

            # Get accuracy (optional but useful)
            accuracy = move_data["accuracy"] if move_data["accuracy"] else 100

            # Get PP (Power Points)
            pp = move_data["pp"] if move_data["pp"] else 0

            # Get English description
            description = "No description available."
            for entry in move_data["flavor_text_entries"]:
                if entry["language"]["name"] == "en" and entry["version_group"]["name"] == "red-blue":
                    description = entry["flavor_text"].replace("\n", " ").replace("\f", " ")
                    break

            # Get effect (short description)
            effect = ""
            if move_data["effect_entries"]:
                for entry in move_data["effect_entries"]:
                    if entry["language"]["name"] == "en":
                        effect = entry["short_effect"]
                        break

            # Store move data
            moves_dict[move_name] = {
                "power": power,
                "type": move_type,
                "category": category,
                "accuracy": accuracy,
                "pp": pp,
                "effect": effect if effect else description
            }

            print(f"✓ {move_name.replace('-', ' ').title()} - {move_type} ({category}) - Power: {power}")

            # Be nice to the API
            time.sleep(0.3)

        except Exception as e:
            print(f"✗ Error fetching {move_name}: {e}")
            continue

    # Save to file
    with open("moves.json", "w", encoding="utf-8") as f:
        json.dump(moves_dict, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Successfully generated moves.json with {len(moves_dict)} moves!")
    print("File saved in the current directory.")

    # Print some stats
    physical_moves = sum(1 for m in moves_dict.values() if m["category"] == "physical")
    special_moves = sum(1 for m in moves_dict.values() if m["category"] == "special")
    status_moves = sum(1 for m in moves_dict.values() if m["category"] == "status")

    print(f"\n📊 Move Statistics:")
    print(f"   Physical: {physical_moves}")
    print(f"   Special: {special_moves}")
    print(f"   Status: {status_moves}")

if __name__ == "__main__":
    generate_kanto_moves()