import requests
import json
import time

def generate_pokemon_battle_data():
    """
    Fetches data for all 151 Kanto Pokémon from PokéAPI
    and generates a pokemon_data.json file formatted for battles.
    """
    pokemon_battle_data = {}

    print("Fetching Kanto Pokémon battle data from PokéAPI...")
    print("This will take about 2-3 minutes...\n")

    # Kanto region: Pokémon #1-151
    for pokemon_id in range(1, 152):
        try:
            # Fetch Pokémon data
            response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}")
            pokemon_data = response.json()

            # Get name
            name = pokemon_data["name"]

            # Get types
            types = [t["type"]["name"].capitalize() for t in pokemon_data["types"]]

            # Get base stats
            base_stats = {}
            for stat in pokemon_data["stats"]:
                stat_name = stat["stat"]["name"]
                if stat_name == "hp":
                    base_stats["hp"] = stat["base_stat"]
                elif stat_name == "attack":
                    base_stats["attack"] = stat["base_stat"]
                elif stat_name == "defense":
                    base_stats["defense"] = stat["base_stat"]
                elif stat_name == "special-attack":
                    base_stats["sp_atk"] = stat["base_stat"]
                elif stat_name == "special-defense":
                    base_stats["sp_def"] = stat["base_stat"]
                elif stat_name == "speed":
                    base_stats["speed"] = stat["base_stat"]

            # Get moves (filter to only get level-up moves from Gen 1)
            moves_list = []
            for move_entry in pokemon_data["moves"]:
                move_name = move_entry["move"]["name"]

                # Check if move is learned via level-up in any Gen 1 game
                for version_detail in move_entry["version_group_details"]:
                    version_group = version_detail["version_group"]["name"]
                    learn_method = version_detail["move_learn_method"]["name"]

                    # Only include level-up moves from Red/Blue/Yellow
                    if learn_method == "level-up" and version_group in ["red-blue", "yellow"]:
                        if move_name not in moves_list:
                            moves_list.append(move_name)
                        break

            # Limit to first 10 moves if there are too many
            if len(moves_list) > 10:
                moves_list = moves_list[:10]

            # If no moves found, add basic moves
            if not moves_list:
                moves_list = ["tackle", "growl"]

            # Capitalize move names for consistency
            moves_list = [move.replace("-", " ").title() for move in moves_list]

            # Build Pokémon entry
            pokemon_battle_data[name] = {
                "types": types,
                "base_stats": base_stats,
                "moves": moves_list
            }

            print(f"✓ #{pokemon_id:03d} {name.capitalize()} - Types: {', '.join(types)} - Moves: {len(moves_list)}")

            # Be respectful to the API
            time.sleep(0.4)

        except Exception as e:
            print(f"✗ Error fetching #{pokemon_id}: {e}")
            continue

    # Save to file
    with open("pokemon_data.json", "w", encoding="utf-8") as f:
        json.dump(pokemon_battle_data, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Successfully generated pokemon_data.json with {len(pokemon_battle_data)} Pokémon!")
    print("File saved in the current directory.")
    print("\nFormat includes:")
    print("  - Types (for type effectiveness)")
    print("  - Base stats (HP, Attack, Defense, Sp.Atk, Sp.Def, Speed)")
    print("  - Moves (level-up moves from Gen 1)")

if __name__ == "__main__":
    generate_pokemon_battle_data()