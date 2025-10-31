import requests
import json
import time

def generate_kanto_pokedex():
    """
    Fetches data for all 151 Kanto Pokémon from PokéAPI
    and generates a pokedex_data.json file.
    """
    pokedex = {}

    print("Fetching Kanto Pokémon data from PokéAPI...")
    print("This may take a few minutes...\n")

    # Kanto region: Pokémon #1-151
    for pokemon_id in range(1, 152):
        try:
            # Fetch Pokémon data
            response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}")
            pokemon_data = response.json()

            # Fetch species data for description and evolution
            species_response = requests.get(f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_id}")
            species_data = species_response.json()

            # Get English name
            name = pokemon_data["name"]

            # Get types
            types = [t["type"]["name"].capitalize() for t in pokemon_data["types"]]

            # Get stats
            stats = {}
            for stat in pokemon_data["stats"]:
                stat_name = stat["stat"]["name"]
                if stat_name == "hp":
                    stats["hp"] = stat["base_stat"]
                elif stat_name == "attack":
                    stats["attack"] = stat["base_stat"]
                elif stat_name == "defense":
                    stats["defense"] = stat["base_stat"]
                elif stat_name == "special-attack":
                    stats["sp_atk"] = stat["base_stat"]
                elif stat_name == "special-defense":
                    stats["sp_def"] = stat["base_stat"]
                elif stat_name == "speed":
                    stats["speed"] = stat["base_stat"]

            # Get abilities
            abilities = [a["ability"]["name"].replace("-", " ").title() 
                        for a in pokemon_data["abilities"]]

            # Get height (decimeters to meters)
            height = f"{pokemon_data['height'] / 10:.1f} m"

            # Get weight (hectograms to kg)
            weight = f"{pokemon_data['weight'] / 10:.1f} kg"

            # Get English description
            description = "A mysterious Pokémon."
            for entry in species_data["flavor_text_entries"]:
                if entry["language"]["name"] == "en":
                    description = entry["flavor_text"].replace("\n", " ").replace("\f", " ")
                    break

            # Get category/genus
            category = "Unknown Pokémon"
            for genus in species_data["genera"]:
                if genus["language"]["name"] == "en":
                    category = genus["genus"]
                    break

            # Get gender ratio
            gender_rate = species_data["gender_rate"]
            if gender_rate == -1:
                gender_ratio = "Genderless"
            else:
                female_percent = (gender_rate / 8) * 100
                male_percent = 100 - female_percent
                gender_ratio = f"♂ {male_percent:.1f}% / ♀ {female_percent:.1f}%"

            # Get evolution chain (simplified)
            evolution = "Does not evolve"
            try:
                evo_chain_url = species_data["evolution_chain"]["url"]
                evo_response = requests.get(evo_chain_url)
                evo_data = evo_response.json()

                # Build evolution chain
                chain = []
                current = evo_data["chain"]

                while current:
                    chain.append(current["species"]["name"].capitalize())
                    if current["evolves_to"]:
                        current = current["evolves_to"][0]
                    else:
                        current = None

                if len(chain) > 1:
                    evolution = " → ".join(chain)
            except:
                pass

            # Official artwork URL
            image_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{pokemon_id}.png"

            # Build Pokémon entry
            pokedex[name] = {
                "number": pokemon_id,
                "name": name.capitalize(),
                "types": types,
                "category": category,
                "height": height,
                "weight": weight,
                "description": description,
                "abilities": abilities,
                "gender_ratio": gender_ratio,
                "base_stats": stats,
                "evolution": evolution,
                "generation": 1,
                "image_url": image_url
            }

            print(f"✓ #{pokemon_id:03d} {name.capitalize()}")

            # Be respectful to the API - small delay
            time.sleep(0.5)

        except Exception as e:
            print(f"✗ Error fetching #{pokemon_id}: {e}")
            continue

    # Save to file
    with open("pokedex_data.json", "w", encoding="utf-8") as f:
        json.dump(pokedex, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Successfully generated pokedex_data.json with {len(pokedex)} Pokémon!")
    print("File saved in the current directory.")

if __name__ == "__main__":
    generate_kanto_pokedex()