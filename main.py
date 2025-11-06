import discord
from discord.ext import commands, tasks
import os
import json
import random
from dotenv import load_dotenv
from keep_alive import keep_alive
import asyncio
from PIL import Image
import requests
from io import BytesIO


# --- Basic Setup ---
load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Required to get user objects from mentions
bot = commands.Bot(command_prefix="!", intents=intents)
# Add this line to disable the default help command
bot.help_command = None

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Pokémon Bot Commands", color=discord.Color.blue())    
    embed.add_field(name="!start", value="Start your Pokémon journey.", inline=False)
    embed.add_field(name="!choose <pokemon>", value="Choose your starter Pokémon (bulbasaur, charmander, squirtle).",
                    inline=False)
    embed.add_field(name="!info", value="Show details of your selected Pokémon.", inline=False)
    embed.add_field(name="!team", value="Show your Pokémon team.", inline=False)
    embed.add_field(name="!select <position>", value="Select a Pokémon from your team.", inline=False)
    embed.add_field(name="!battle <opponent>", value="Challenge another player to a battle.", inline=False)
    embed.add_field(name="!accept", value="Accept a battle challenge.", inline=False)
    embed.add_field(name="!fight <move>", value="Use a move in battle.", inline=False)
    embed.add_field(name="!forfeit", value="Forfeit the current battle.", inline=False)
    await ctx.send(embed=embed)

    
# --- Constants ---
USER_DATA_FILE = "user_data.json"
POKEMON_DATA_FILE = "pokemon_data.json"
MOVES_DATA_FILE = "moves.json"
USER_BALANCE_FILE = "user_balance.json"
SAVE_INTERVAL_SECONDS = 60
POKEBALL_EMOJIS = {
    "pokeball": "<:pokeball:1434234039363178577>",      # Replace with actual ID
    "greatball": "<:pokeball1:1434234047332221151>",    # Replace with actual ID
    "ultraball": "<:ultraball:1434234042131157024>",    # Replace with actual ID
    "masterball": "<:masterball:1434234044819836968>"   # Replace with actual ID
}

TYPE_CHART = {
    "normal": {"rock": 0.5, "ghost": 0, "steel": 0.5},
    "fire": {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 2, "bug": 2, "rock": 0.5, "dragon": 0.5, "steel": 2},
    "water": {"fire": 2, "water": 0.5, "grass": 0.5, "ground": 2, "rock": 2, "dragon": 0.5},
    "electric": {"water": 2, "electric": 0.5, "grass": 0.5, "ground": 0, "flying": 2, "dragon": 0.5},
    "grass": {"fire": 0.5, "water": 2, "grass": 0.5, "poison": 0.5, "ground": 2, "flying": 0.5, "bug": 0.5, "rock": 2, "dragon": 0.5, "steel": 0.5},
    "ice": {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 0.5, "ground": 2, "flying": 2, "dragon": 2, "steel": 0.5},
    "fighting": {"normal": 2, "ice": 2, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2, "ghost": 0, "dark": 2, "steel": 2, "fairy": 0.5},
    "poison": {"grass": 2, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0, "fairy": 2},
    "ground": {"fire": 2, "electric": 2, "grass": 0.5, "poison": 2, "flying": 0, "bug": 0.5, "rock": 2, "steel": 2},
    "flying": {"electric": 0.5, "grass": 2, "fighting": 2, "bug": 2, "rock": 0.5, "steel": 0.5},
    "psychic": {"fighting": 2, "poison": 2, "psychic": 0.5, "dark": 0, "steel": 0.5},
    "bug": {"fire": 0.5, "grass": 2, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2, "ghost": 0.5, "dark": 2, "steel": 0.5, "fairy": 0.5},
    "rock": {"fire": 2, "ice": 2, "fighting": 0.5, "ground": 0.5, "flying": 2, "bug": 2, "steel": 0.5},
    "ghost": {"normal": 0, "psychic": 2, "ghost": 2, "dark": 0.5},
    "dragon": {"dragon": 2, "steel": 0.5, "fairy": 0},
    "dark": {"fighting": 0.5, "psychic": 2, "ghost": 2, "dark": 0.5, "fairy": 0.5},
    "steel": {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2, "rock": 2, "steel": 0.5, "fairy": 2},
    "fairy": {"fire": 0.5, "fighting": 2, "poison": 0.5, "dragon": 2, "dark": 2, "steel": 0.5}
}
# Spawn system constants
SPAWN_BASE_MESSAGES = 35  # Base messages needed for spawn
SPAWN_ACTIVE_THRESHOLD = 5  # Users active in last 5 minutes
SPAWN_ACTIVE_MESSAGES = 25  # Messages needed when server is active
MAX_CATCH_ATTEMPTS = 3

# Pokemon rarity configuration
RARITY_TIERS = {
    "common": {
        "spawn_weight": 50,
        "catch_rate": 90,
        "ball_required": "pokeball",
        "pokemon": ["pidgey", "rattata", "weedle", "caterpie", "spearow", "ekans", "sandshrew", "zubat", "oddish", "paras", "venonat", "diglett", "meowth", "psyduck", "poliwag", "bellsprout", "tentacool", "geodude", "magikarp", "goldeen", "staryu", "eevee"]
    },
    "uncommon": {
        "spawn_weight": 30,
        "catch_rate": 75,
        "ball_required": "pokeball",
        "pokemon": ["bulbasaur", "charmander", "squirtle", "pikachu", "nidoran-f", "nidoran-m", "clefairy", "jigglypuff", "mankey", "growlithe", "machop", "ponyta", "slowpoke", "farfetchd", "seel", "grimer", "shellder", "gastly", "onix", "drowzee", "krabby", "voltorb", "exeggcute", "cubone", "lickitung", "koffing", "rhyhorn", "tangela", "horsea", "mr-mime"]
    },
    "rare": {
        "spawn_weight": 15,
        "catch_rate": 60,
        "ball_required": "greatball",
        "pokemon": ["nidorina", "nidorino", "vulpix", "gloom", "persian", "golduck", "primeape", "arcanine", "poliwhirl", "kadabra", "machoke", "weepinbell", "graveler", "rapidash", "slowbro", "magneton", "dodrio", "dewgong", "haunter", "hypno", "kingler", "electrode", "exeggutor", "marowak", "hitmonlee", "hitmonchan", "chansey", "kangaskhan", "seadra", "seaking", "starmie", "jynx", "electabuzz", "magmar", "pinsir", "tauros", "porygon"]
    },
    "epic": {
        "spawn_weight": 4,
        "catch_rate": 45,
        "ball_required": "ultraball",
        "pokemon": ["ivysaur", "charmeleon", "wartortle", "raichu", "nidoqueen", "nidoking", "ninetales", "wigglytuff", "vileplume", "dugtrio", "venomoth", "alakazam", "machamp", "victreebel", "golem", "muk", "cloyster", "gengar", "weezing", "rhydon", "gyarados", "lapras", "ditto", "vaporeon", "jolteon", "flareon", "omastar", "kabutops", "aerodactyl", "snorlax"]
    },
    "legendary": {
        "spawn_weight": 0.8,
        "catch_rate": 30,
        "ball_required": "ultraball",
        "pokemon": ["venusaur", "charizard", "blastoise", "articuno", "zapdos", "moltres", "dragonite"]
    },
    "mythical": {
        "spawn_weight": 0.2,
        "catch_rate": 15,
        "ball_required": "masterball",
        "pokemon": ["mew", "mewtwo"]
    }
}

# Evolution data
EVOLUTION_DATA = {
    "bulbasaur": {"evolves_to": "ivysaur", "level": 16},
    "ivysaur": {"evolves_to": "venusaur", "level": 32},
    "charmander": {"evolves_to": "charmeleon", "level": 16},
    "charmeleon": {"evolves_to": "charizard", "level": 36},
    "squirtle": {"evolves_to": "wartortle", "level": 16},
    "wartortle": {"evolves_to": "blastoise", "level": 36},
    "caterpie": {"evolves_to": "metapod", "level": 7},
    "metapod": {"evolves_to": "butterfree", "level": 10},
    "weedle": {"evolves_to": "kakuna", "level": 7},
    "kakuna": {"evolves_to": "beedrill", "level": 10},
    "pidgey": {"evolves_to": "pidgeotto", "level": 18},
    "pidgeotto": {"evolves_to": "pidgeot", "level": 36},
    "rattata": {"evolves_to": "raticate", "level": 20},
    "spearow": {"evolves_to": "fearow", "level": 20},
    "ekans": {"evolves_to": "arbok", "level": 22},
    "pikachu": {"evolves_to": "raichu", "level": 22},
    "sandshrew": {"evolves_to": "sandslash", "level": 22},
    "nidoran-f": {"evolves_to": "nidorina", "level": 16},
    "nidorina": {"evolves_to": "nidoqueen", "level": 36},
    "nidoran-m": {"evolves_to": "nidorino", "level": 16},
    "nidorino": {"evolves_to": "nidoking", "level": 36},
    "oddish": {"evolves_to": "gloom", "level": 21},
    "gloom": {"evolves_to": "vileplume", "level": 36},
    "zubat": {"evolves_to": "golbat", "level": 22},
    "machop": {"evolves_to": "machoke", "level": 28},
    "machoke": {"evolves_to": "machamp", "level": 40},
    "geodude": {"evolves_to": "graveler", "level": 25},
    "graveler": {"evolves_to": "golem", "level": 40},
    "gastly": {"evolves_to": "haunter", "level": 25},
    "haunter": {"evolves_to": "gengar", "level": 40},
    "magikarp": {"evolves_to": "gyarados", "level": 20},
    "dratini": {"evolves_to": "dragonair", "level": 30},
    "dragonair": {"evolves_to": "dragonite", "level": 55}
}

# Global spawn tracking
spawn_tracker = {}
active_users = {}
spawned_pokemon = {}


# ============================================
# PART 2: HELPER FUNCTIONS FOR SPAWN SYSTEM
# Add these after your existing helper functions
# ============================================

def get_pokemon_rarity(pokemon_name):
    """Returns the rarity tier of a pokemon."""
    for rarity, data in RARITY_TIERS.items():
        if pokemon_name in data["pokemon"]:
            return rarity
    return "common"

def get_required_ball(rarity):
    """Returns the required ball type for a rarity."""
    return RARITY_TIERS[rarity]["ball_required"]

def get_catch_rate(rarity):
    """Returns the catch rate for a rarity."""
    return RARITY_TIERS[rarity]["catch_rate"]

def spawn_random_pokemon():
    """Spawns a random pokemon based on weighted rarity."""
    weights = []
    pokemon_pool = []

    for rarity, data in RARITY_TIERS.items():
        for poke in data["pokemon"]:
            if poke in pokemon_data:  # Only spawn if we have data
                weights.append(data["spawn_weight"])
                pokemon_pool.append(poke)

    if not pokemon_pool:
        return None

    return random.choices(pokemon_pool, weights=weights, k=1)[0]

def get_moves_for_level(pokemon_name, level):
    """Returns moves a pokemon should know at a given level."""
    all_moves = pokemon_data.get(pokemon_name, {}).get("moves", [])

    # For now, give up to 4 random moves from available pool
    # In production, you'd want level-based move learning
    if len(all_moves) <= 4:
        return all_moves

    return random.sample(all_moves, 4)

def can_evolve(pokemon):
    """Checks if a pokemon can evolve."""
    poke_name = pokemon["name"]
    if poke_name not in EVOLUTION_DATA:
        return False, None

    evo_data = EVOLUTION_DATA[poke_name]
    if pokemon["level"] >= evo_data["level"]:
        return True, evo_data["evolves_to"]

    return False, None

async def evolve_pokemon(pokemon):
    """Evolves a pokemon and updates its stats."""
    can_evo, new_form = can_evolve(pokemon)

    if not can_evo:
        return False, None

    # Update pokemon
    old_name = pokemon["name"]
    pokemon["name"] = new_form

    # Recalculate stats
    pokemon["stats"] = calculate_actual_stats(new_form, pokemon["level"], pokemon["ivs"])
    pokemon["current_hp"] = pokemon["stats"]["HP"]

    # Update moves pool (keep existing moves but allow learning new ones)
    available_moves = pokemon_data.get(new_form, {}).get("moves", [])

    return True, old_name

async def spawn_pokemon_in_channel(channel):
    """Spawns a wild pokemon in the channel."""
    pokemon_name = spawn_random_pokemon()

    if not pokemon_name:
        return

    rarity = get_pokemon_rarity(pokemon_name)
    level = random.randint(1, 30)

    channel_id = str(channel.id)
    spawned_pokemon[channel_id] = {
        "name": pokemon_name,
        "level": level,
        "rarity": rarity,
        "attempts": 0,
        "failed_catchers": set()
    }

    poke_image = pokedex_data.get(pokemon_name, {}).get('image_url', '')
    poke_types = pokemon_data.get(pokemon_name, {}).get('types', ['Unknown'])
    types_str = "/".join(poke_types)

    rarity_emojis = {
        "common": "⚪",
        "uncommon": "🟢",
        "rare": "🔵",
        "epic": "🟣",
        "legendary": "🟠",
        "mythical": "🔴"
    }
    rarity_emoji = rarity_emojis.get(rarity, "⚪")

    embed = discord.Embed(
        title="🌿 A wild Pokémon has appeared!",
        description=f"A wild **{pokemon_name.capitalize()}** appeared!\nType `!catch` to catch it!",
        color=0x00FF00
    )

    if poke_image:
        embed.set_image(url=poke_image)

    embed.add_field(name="Level", value=f"**{level}**", inline=True)
    embed.add_field(name="Type", value=f"**{types_str}**", inline=True)
    embed.add_field(name="Rarity", value=f"{rarity_emoji} **{rarity.capitalize()}**", inline=True)

    required_ball = get_required_ball(rarity)
    ball_names = {"pokeball": "Poké Ball", "greatball": "Great Ball", "ultraball": "Ultra Ball", "masterball": "Master Ball"}
    embed.set_footer(text=f"Required: {ball_names[required_ball]} • Hurry before it runs away!")

    await channel.send(embed=embed)


# --- Global Data Stores ---
user_data = {}
pokemon_data = {}
moves_data = {}
user_balance = {}
active_battles = {} # Key: channel.id, Value: Battle object

# --- Helper Functions ---
def load_data():
    """Loads all necessary data from JSON files into memory."""
    global user_data, pokemon_data, moves_data, user_balance

    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(USER_DATA_FILE, "r") as f:
        # Handle potential empty file error
        try:
            user_data = json.load(f)
        except json.JSONDecodeError:
            user_data = {}

    with open(POKEMON_DATA_FILE, "r") as f:
        pokemon_data = json.load(f)

    with open(MOVES_DATA_FILE, "r") as f:
        moves_data = json.load(f)

    if not os.path.exists(USER_BALANCE_FILE):
        with open(USER_BALANCE_FILE, "w") as f:
            json.dump({}, f)
    with open(USER_BALANCE_FILE, "r") as f:
        try:
            user_balance = json.load(f)
        except json.JSONDecodeError:
            user_balance = {}


def generate_ivs():
    """Generates a dictionary of random IVs for a Pokémon."""
    return {stat: random.randint(0, 31) for stat in ["hp", "attack", "defense", "sp_atk", "sp_def", "speed"]}

def calculate_actual_stats(pokemon_name: str, level: int, ivs: dict):
    """Calculates the display stats of a Pokémon."""
    base = pokemon_data[pokemon_name]["base_stats"]
    return {
        "HP": ((2 * base["hp"] + ivs["hp"]) * level) // 100 + level + 10,
        "Attack": ((2 * base["attack"] + ivs["attack"]) * level) // 100 + 5,
        "Defense": ((2 * base["defense"] + ivs["defense"]) * level) // 100 + 5,
        "Sp. Atk": ((2 * base["sp_atk"] + ivs["sp_atk"]) * level) // 100 + 5,
        "Sp. Def": ((2 * base["sp_def"] + ivs["sp_def"]) * level) // 100 + 5,
        "Speed": ((2 * base["speed"] + ivs["speed"]) * level) // 100 + 5,
    }


def calculate_damage(attacker_pokemon: dict, defender_pokemon: dict, move_name: str):
    """
    Calculates damage using the actual Pokémon damage formula.
    Returns: (damage, type_effectiveness, is_critical, messages_list)
    """
    move_info = moves_data.get(move_name.lower())
    if not move_info:
        return 0, 1.0, False, ["Move not found!"]

    messages = []

    # Get move properties
    move_power = move_info.get("power", 0)
    move_type = move_info.get("type", "Normal").lower()
    move_category = move_info.get("category", "physical").lower()

    # Status moves don't deal damage
    if move_category == "status" or move_power == 0:
        return 0, 1.0, False, [f"{move_name.capitalize()} doesn't deal direct damage!"]

    # Get attacker's level
    level = attacker_pokemon["level"]

    # Determine which stats to use based on move category
    if move_category == "special":
        attack_stat = attacker_pokemon["stats"]["Sp. Atk"]
        defense_stat = defender_pokemon["stats"]["Sp. Def"]
    else:  # physical
        attack_stat = attacker_pokemon["stats"]["Attack"]
        defense_stat = defender_pokemon["stats"]["Defense"]

    # Critical hit (6.25% chance in Gen VI+, deals 1.5x damage)
    is_critical = random.random() < 0.0625
    critical_multiplier = 1.5 if is_critical else 1.0

    # STAB (Same Type Attack Bonus) - 1.5x if move type matches Pokémon type
    attacker_types = pokemon_data.get(attacker_pokemon["name"], {}).get("types", [])
    stab = 1.5 if move_type in [t.lower() for t in attacker_types] else 1.0

    # Type effectiveness
    defender_types = pokemon_data.get(defender_pokemon["name"], {}).get("types", ["normal"])
    type_effectiveness = 1.0

    for def_type in defender_types:
        def_type_lower = def_type.lower()
        if move_type in TYPE_CHART and def_type_lower in TYPE_CHART[move_type]:
            type_effectiveness *= TYPE_CHART[move_type][def_type_lower]

    # Random factor (0.85 to 1.0)
    random_factor = random.uniform(0.85, 1.0)

    # Pokémon Damage Formula (Generation V+)
    # Damage = ((((2 * Level / 5) + 2) * Power * Attack / Defense) / 50 + 2) * Modifiers
    base_damage = (((2 * level / 5) + 2) * move_power * attack_stat / defense_stat) / 50 + 2

    # Apply all multipliers
    final_damage = base_damage * critical_multiplier * stab * type_effectiveness * random_factor
    final_damage = max(1, int(final_damage))  # Minimum 1 damage

    # Generate messages
    if type_effectiveness == 0:
        messages.append("It doesn't affect the foe...")
        final_damage = 0
    elif type_effectiveness >= 2:
        messages.append("It's super effective! 💥")
    elif type_effectiveness > 1:
        messages.append("It's super effective!")
    elif type_effectiveness <= 0.5:
        messages.append("It's not very effective...")

    if is_critical:
        messages.append("A critical hit! ⚡")

    return final_damage, type_effectiveness, is_critical, messages

def create_pokemon(pokemon_name: str, level: int = 5):
    """Creates a new Pokémon dictionary object."""
    ivs = generate_ivs()
    stats = calculate_actual_stats(pokemon_name, level, ivs)
    return {
        "name": pokemon_name,
        "level": level,
        "xp": 0,
        "gender": random.choice(["Male", "Female"]),
        "nature": random.choice(["Adamant", "Bold", "Brave", "Calm", "Gentle", "Hardy", "Jolly", "Modest", "Quiet", "Timid"]),
        "ivs": ivs,
        "stats": stats,
        "current_hp": stats["HP"],
        "moves": pokemon_data[pokemon_name]["moves"][:4] # Take up to 4 moves
    }

def migrate_user_data_format():
    """
    One-time migration script.
    Converts old user data format (flat structure) to the new team-based format.
    """
    data_migrated = False
    for user_id, player_data in list(user_data.items()): # Use list to allow modification during iteration
        # Check for the old format key "starter" at the top level
        if "starter" in player_data and "pokemons" not in player_data:
            print(f"Migrating data for user {user_id}...")
            data_migrated = True

            starter_name = player_data["starter"]
            # Ensure starter_name exists in pokemon_data to avoid errors
            if starter_name not in pokemon_data:
                print(f"  - Skipping user {user_id}, starter '{starter_name}' not found in pokemon_data.json")
                continue

            level = player_data.get("level", 5)
            ivs = player_data.get("ivs", generate_ivs())

            # Recalculate stats to ensure they are correct and consistent
            stats = calculate_actual_stats(starter_name, level, ivs)

            migrated_pokemon = {
                "name": starter_name,
                "level": level,
                "xp": player_data.get("xp", 0),
                "gender": player_data.get("gender", random.choice(["Male", "Female"])),
                "nature": player_data.get("nature", random.choice(["Adamant", "Bold", "Brave"])),
                "ivs": ivs,
                "stats": stats,
                "current_hp": stats["HP"], # Set current HP to max HP
                "moves": pokemon_data.get(starter_name, {}).get("moves", [])[:4]
            }

            # Create the new user data structure
            user_data[user_id] = {
                "pokemons": [migrated_pokemon],
                "selected_pokemon_index": 0,
                "items": {} # Add items field for future use
            }

    if data_migrated:
        print("Data migration complete. Saving new format to disk.")
        with open(USER_DATA_FILE, "w") as f:
            json.dump(user_data, f, indent=4)

# --- Battle System Class ---
# ============================================
# UPDATED BATTLE SYSTEM CLASS - REPLACE YOUR ENTIRE Battle CLASS
# ============================================

# ============================================
# COMPLETE BATTLE CLASS - REPLACE YOUR ENTIRE Battle CLASS
# ============================================

class Battle:
    def __init__(self, challenger: discord.Member, opponent: discord.Member, channel: discord.TextChannel):
        """Initializes the battle state with simultaneous turn system."""
        self.challenger = challenger
        self.opponent = opponent
        self.channel = channel
        self.game_over = False

        # Move selection storage
        self.challenger_move = None
        self.opponent_move = None
        self.move_selection_active = False

        # Get selected Pokémon from user data and CREATE COPIES for the battle
        challenger_data = user_data[str(challenger.id)]
        self.challenger_pokemon = dict(challenger_data["pokemons"][challenger_data["selected_pokemon_index"]])
        if self.challenger_pokemon["current_hp"] <= 0:
            self.challenger_pokemon["current_hp"] = self.challenger_pokemon["stats"]["HP"]

        opponent_data = user_data[str(opponent.id)]
        self.opponent_pokemon = dict(opponent_data["pokemons"][opponent_data["selected_pokemon_index"]])
        if self.opponent_pokemon["current_hp"] <= 0:
            self.opponent_pokemon["current_hp"] = self.opponent_pokemon["stats"]["HP"]

    def get_hp_bar(self, current_hp: int, max_hp: int, length: int = 20) -> str:
        """Creates a visual HP bar."""
        percentage = current_hp / max_hp
        filled = int(length * percentage)

        # Color based on HP percentage
        if percentage > 0.5:
            bar_char = "█"  # Green/full
        elif percentage > 0.2:
            bar_char = "▓"  # Yellow/medium
        else:
            bar_char = "░"  # Red/low

        empty_char = "░"
        bar = bar_char * filled + empty_char * (length - filled)
        return f"`{bar}` {current_hp}/{max_hp} HP"




    async def create_side_by_side_image(self):
        """
        Creates a single image with both Pokémon side by side.
        Returns a discord.File object or None if failed.
        """
        try:
            cp_image_url = pokedex_data.get(self.challenger_pokemon['name'], {}).get('image_url')
            op_image_url = pokedex_data.get(self.opponent_pokemon['name'], {}).get('image_url')

            if not cp_image_url or not op_image_url:
                return None

            # Download both images
            print(f"Downloading images for battle...")
            response1 = requests.get(cp_image_url, timeout=5)
            response2 = requests.get(op_image_url, timeout=5)

            # Open images
            img1 = Image.open(BytesIO(response1.content)).convert('RGBA')
            img2 = Image.open(BytesIO(response2.content)).convert('RGBA')

            # Resize both to same height (300px)
            target_height = 300

            # Resize image 1
            ratio1 = target_height / img1.height
            new_width1 = int(img1.width * ratio1)
            img1_resized = img1.resize((new_width1, target_height), Image.Resampling.LANCZOS)

            # Resize image 2
            ratio2 = target_height / img2.height
            new_width2 = int(img2.width * ratio2)
            img2_resized = img2.resize((new_width2, target_height), Image.Resampling.LANCZOS)

            # Create combined image with space between
            gap = 100  # Space between Pokémon
            total_width = new_width1 + gap + new_width2

            # Create transparent background
            combined = Image.new('RGBA', (total_width, target_height), (0, 0, 0, 0))

            # Paste images side by side
            combined.paste(img1_resized, (0, 0), img1_resized)
            combined.paste(img2_resized, (new_width1 + gap, 0), img2_resized)

            # Save to bytes
            output = BytesIO()
            combined.save(output, format='PNG')
            output.seek(0)

            print(f"✓ Combined battle image created successfully!")
            return discord.File(output, filename='battle_scene.png')

        except Exception as e:
            print(f"✗ Error creating battle image: {e}")
            return None


    

    async def show_battle_status(self, message: str = ""):
        """Sends an embed with the current battle status to the channel."""

        # Get Pokémon data
        cp = self.challenger_pokemon
        cp_name = cp['name'].capitalize()
        cp_types = " | ".join(pokemon_data.get(cp['name'], {}).get('types', ['Normal']))

        op = self.opponent_pokemon
        op_name = op['name'].capitalize()
        op_types = " | ".join(pokemon_data.get(op['name'], {}).get('types', ['Normal']))

        # Create the embed
        embed = discord.Embed(
            title=f"⚔️ {cp_name} vs {op_name}",
            description=f"**{self.challenger.display_name}** vs **{self.opponent.display_name}**\n{message if message else ''}",
            color=discord.Color.blue()
        )

        # Left column - Challenger
        challenger_info = (
            f"**Level {cp['level']}**\n"
            f"**Type:** {cp_types}\n"
            f"{self.get_hp_bar(cp['current_hp'], cp['stats']['HP'])}"
        )
        embed.add_field(name=f"🔵 {self.challenger.display_name}", value=challenger_info, inline=True)

        # Middle spacer
        embed.add_field(name="⚔️", value="VS", inline=True)

        # Right column - Opponent
        opponent_info = (
            f"**Level {op['level']}**\n"
            f"**Type:** {op_types}\n"
            f"{self.get_hp_bar(op['current_hp'], op['stats']['HP'])}"
        )
        embed.add_field(name=f"🔴 {self.opponent.display_name}", value=opponent_info, inline=True)

        embed.set_footer(text="⏱️ You have 10 seconds to choose your move in DMs!")

        # Create combined side-by-side image
        battle_image = await self.create_side_by_side_image()

        if battle_image:
            # Use the combined image
            embed.set_image(url="attachment://battle_scene.png")
            await self.channel.send(embed=embed, file=battle_image)
        else:
            # Fallback: use separate images
            cp_image = pokedex_data.get(cp['name'], {}).get('image_url')
            op_image = pokedex_data.get(op['name'], {}).get('image_url')

            if cp_image:
                embed.set_image(url=cp_image)
            if op_image:
                embed.set_thumbnail(url=op_image)

            await self.channel.send(embed=embed)

    async def send_move_choices_dm(self, player: discord.Member, pokemon: dict):
        """Sends available moves to player's DM."""
        try:
            moves_list = "\n".join([f"• **{move}**" for move in pokemon['moves']])

            embed = discord.Embed(
                title=f"⚔️ Battle Move Selection",
                description=f"Your {pokemon['name'].capitalize()} can use:",
                color=discord.Color.gold()
            )
            embed.add_field(name="Available Moves", value=moves_list, inline=False)
            embed.add_field(
                name="How to choose:",
                value=f"Reply here in DM with: `!fight <move name>`\n**You have 10 seconds!**",
                inline=False
            )

            await player.send(embed=embed)
            print(f"✓ DM sent successfully to {player.display_name}")
            return True

        except discord.Forbidden:
            print(f"✗ Cannot DM {player.display_name} - DMs are closed")
            await self.channel.send(f"⚠️ {player.mention}, I can't DM you! Please enable DMs from server members.")
            return False
        except Exception as e:
            print(f"✗ Error sending DM to {player.display_name}: {e}")
            await self.channel.send(f"⚠️ Error sending DM to {player.mention}: {e}")
            return False

    async def request_moves(self):
        """Requests moves from both players via DM."""
        if self.game_over:
            return False

        print(f"Requesting moves from {self.challenger.display_name} and {self.opponent.display_name}")

        self.move_selection_active = True
        self.challenger_move = None
        self.opponent_move = None

        


        # Send move options to both players
        await self.show_battle_status("📨 Sending move selections to your DMs...")

        await asyncio.sleep(0.5)

        dm_sent_challenger = await self.send_move_choices_dm(self.challenger, self.challenger_pokemon)
        dm_sent_opponent = await self.send_move_choices_dm(self.opponent, self.opponent_pokemon)

        if not dm_sent_challenger or not dm_sent_opponent:
            await self.channel.send("❌ Battle cancelled due to DM issues. Make sure your DMs are open!")
            self.game_over = True
            if self.channel.id in active_battles:
                del active_battles[self.channel.id]
            return False

        await self.channel.send("✅ Move selections sent! Check your DMs!")

        # Wait 10 seconds for both players to choose
        print("Waiting 10 seconds for move selection...")
        await asyncio.sleep(10)

        if self.game_over:
            return False

        self.move_selection_active = False

        print(f"Challenger move: {self.challenger_move}, Opponent move: {self.opponent_move}")

        # Process the turn
        await self.execute_turn()
        return True

    async def process_move_from_dm(self, player: discord.Member, move_name: str):
        """Processes a move selection from DM."""
        if self.game_over:
            await player.send("❌ This battle has already ended!")
            return False

        if not self.move_selection_active:
            await player.send("⏱️ Move selection is not currently active!")
            return False

        if player == self.challenger:
            if self.challenger_move is None:
                if move_name.lower() in [m.lower() for m in self.challenger_pokemon["moves"]]:
                    self.challenger_move = move_name
                    await player.send(f"✅ You selected **{move_name.capitalize()}**!")
                    return True
                else:
                    await player.send(f"❌ Your {self.challenger_pokemon['name'].capitalize()} doesn't know that move!")
                    return False
        elif player == self.opponent:
            if self.opponent_move is None:
                if move_name.lower() in [m.lower() for m in self.opponent_pokemon["moves"]]:
                    self.opponent_move = move_name
                    await player.send(f"✅ You selected **{move_name.capitalize()}**!")
                    return True
                else:
                    await player.send(f"❌ Your {self.opponent_pokemon['name'].capitalize()} doesn't know that move!")
                    return False
        return False

    async def execute_turn(self):
        """Executes the turn after both players have selected moves."""
        if self.game_over:
            return

        # Check if both players selected moves
        if self.challenger_move is None:
            await self.channel.send(f"⏱️ {self.challenger.mention} didn't select a move in time!")

        if self.opponent_move is None:
            await self.channel.send(f"⏱️ {self.opponent.mention} didn't select a move in time!")

        # If neither selected, end turn
        if self.challenger_move is None and self.opponent_move is None:
            await self.channel.send("💤 Both players passed! Requesting moves again...")
            await self.request_moves()
            return

        # Determine order based on speed (faster goes first)
        challenger_speed = self.challenger_pokemon['stats']['Speed']
        opponent_speed = self.opponent_pokemon['stats']['Speed']

        # Create attack order
        if challenger_speed > opponent_speed:
            first_attacker = self.challenger
            first_move = self.challenger_move
            second_attacker = self.opponent
            second_move = self.opponent_move
        elif opponent_speed > challenger_speed:
            first_attacker = self.opponent
            first_move = self.opponent_move
            second_attacker = self.challenger
            second_move = self.challenger_move
        else:
            # Same speed - random
            if random.choice([True, False]):
                first_attacker = self.challenger
                first_move = self.challenger_move
                second_attacker = self.opponent
                second_move = self.opponent_move
            else:
                first_attacker = self.opponent
                first_move = self.opponent_move
                second_attacker = self.challenger
                second_move = self.challenger_move

        # Execute first attack
        if first_move:
            fainted = await self.execute_attack(first_attacker, first_move)
            if fainted or self.game_over:
                return

        await asyncio.sleep(1)

        # Execute second attack
        if second_move:
            fainted = await self.execute_attack(second_attacker, second_move)
            if fainted or self.game_over:
                return

        # If battle still going, request next moves
        if not self.game_over:
            await asyncio.sleep(1.5)
            await self.request_moves()

    async def execute_attack(self, attacker: discord.Member, move_name: str):
        """Executes a single attack and returns True if defender fainted."""

        # Determine attacker and defender
        if attacker == self.challenger:
            attacker_pokemon = self.challenger_pokemon
            defender_pokemon = self.opponent_pokemon
            defender = self.opponent
        else:
            attacker_pokemon = self.opponent_pokemon
            defender_pokemon = self.challenger_pokemon
            defender = self.challenger

        # Normalize move name for lookup
        move_lookup_name = move_name.lower().replace(" ", "-")
        move_info = moves_data.get(move_lookup_name)

        if not move_info:
            await self.channel.send(f"❌ Move '{move_name}' not found!")
            return False

        # Calculate damage
        damage, type_eff, is_crit, effect_messages = calculate_damage(
            attacker_pokemon, defender_pokemon, move_name
        )

        # Get move details
        move_type = move_info.get("type", "Normal")
        move_category = move_info.get("category", "Physical").capitalize()
        category_emoji = "⚔️" if move_category.lower() == "physical" else "✨" if move_category.lower() == "special" else "🛡️"

        # Create attack embed
        embed = discord.Embed(color=discord.Color.red())
        embed.add_field(
            name=f"{attacker.display_name}'s {attacker_pokemon['name'].capitalize()} used {move_name.capitalize()}! {category_emoji}",
            value=f"**Type:** {move_type} • **Category:** {move_category}",
            inline=False
        )

        # Apply damage
        defender_pokemon["current_hp"] = max(0, defender_pokemon["current_hp"] - damage)

        # Add damage info
        if damage > 0:
            damage_text = f"💥 **{damage} damage** to {defender.display_name}'s {defender_pokemon['name'].capitalize()}!"
            if effect_messages:
                damage_text += "\n" + "\n".join(effect_messages)
            embed.add_field(name="Result", value=damage_text, inline=False)
        else:
            if effect_messages:
                embed.add_field(name="Result", value="\n".join(effect_messages), inline=False)

        # Show HP bars
        embed.add_field(
            name=f"{defender_pokemon['name'].capitalize()}'s HP",
            value=self.get_hp_bar(defender_pokemon['current_hp'], defender_pokemon['stats']['HP']),
            inline=False
        )

        await self.channel.send(embed=embed)

        # Check if defender fainted
        if defender_pokemon["current_hp"] <= 0:
            defender_pokemon["current_hp"] = 0
            self.game_over = True
            await asyncio.sleep(1)
            await self.channel.send(f"💀 {defender.display_name}'s {defender_pokemon['name'].capitalize()} fainted!")
            await self.end_battle(winner=attacker, loser=defender)
            return True

        return False

    async def end_battle(self, winner, loser):
        """Ends the battle and declares a winner."""
        embed = discord.Embed(
            title="🏆 Battle Ended!",
            description=f"**{winner.display_name}** wins the battle!",
            color=discord.Color.gold()
        )

        winner_pokemon = self.challenger_pokemon if winner == self.challenger else self.opponent_pokemon
        embed.set_thumbnail(url=pokedex_data.get(winner_pokemon['name'], {}).get('image_url', ''))
        embed.add_field(
            name="Victory!",
            value=f"{winner_pokemon['name'].capitalize()} (Lv.{winner_pokemon['level']}) is victorious!",
            inline=False
        )

        await self.channel.send(embed=embed)

        # Clean up
        if self.channel.id in active_battles:
            del active_battles[self.channel.id]




# --- Bot Events ---
@bot.event
async def on_ready():
    load_data()
    migrate_user_data_format() # <-- MIGRATION SCRIPT RUNS HERE
    save_user_data.start()
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Process commands first
    await bot.process_commands(message)

    # Handle DM messages for battle move selection
    if isinstance(message.channel, discord.DMChannel):
        for channel_id, battle in active_battles.items():
            if isinstance(battle, Battle):
                if message.author in [battle.challenger, battle.opponent]:
                    if message.content.startswith("!fight "):
                        move_name = message.content[7:].strip()
                        await battle.process_move_from_dm(message.author, move_name)
                    return

    # Skip spawn system for DMs
    if isinstance(message.channel, discord.DMChannel):
        return

    guild_id = str(message.guild.id)
    channel_id = str(message.channel.id)
    user_id = str(message.author.id)

    # Track active users
    current_time = asyncio.get_event_loop().time()
    if guild_id not in active_users:
        active_users[guild_id] = {}
    active_users[guild_id][user_id] = current_time

    # Clean up old active users (older than 5 minutes)
    cutoff_time = current_time - 300
    active_users[guild_id] = {uid: time for uid, time in active_users[guild_id].items() if time > cutoff_time}

    # Initialize spawn tracker for this channel
    if channel_id not in spawn_tracker:
        spawn_tracker[channel_id] = {"messages": 0, "last_spawn": 0}

    spawn_tracker[channel_id]["messages"] += 1

    # Determine spawn threshold based on server activity
    active_user_count = len(active_users.get(guild_id, {}))
    threshold = SPAWN_ACTIVE_MESSAGES if active_user_count >= SPAWN_ACTIVE_THRESHOLD else SPAWN_BASE_MESSAGES

    # Check if we should spawn
    if spawn_tracker[channel_id]["messages"] >= threshold:
        # Check if there's already a pokemon spawned in this channel
        if channel_id not in spawned_pokemon:
            await spawn_pokemon_in_channel(message.channel)
            spawn_tracker[channel_id]["messages"] = 0
            spawn_tracker[channel_id]["last_spawn"] = current_time

    # XP gain system for selected pokemon
    if user_id in user_data and user_data[user_id].get("pokemons"):
        player_data = user_data[user_id]
        if 0 <= player_data["selected_pokemon_index"] < len(player_data["pokemons"]):
            selected_pokemon = player_data["pokemons"][player_data["selected_pokemon_index"]]

            selected_pokemon["xp"] += 5
            if selected_pokemon["xp"] >= 100:
                selected_pokemon["xp"] -= 100
                selected_pokemon["level"] += 1

                # Recalculate stats
                selected_pokemon["stats"] = calculate_actual_stats(
                    selected_pokemon["name"], 
                    selected_pokemon["level"], 
                    selected_pokemon["ivs"]
                )
                selected_pokemon["current_hp"] = selected_pokemon["stats"]["HP"]

                await message.channel.send(
                    f"🎉 Congrats {message.author.mention}! Your {selected_pokemon['name'].capitalize()} is now **Level {selected_pokemon['level']}**!"
                )


                # Check for evolution
                can_evo, new_form = can_evolve(selected_pokemon)
                if can_evo:
                    old_name = selected_pokemon['name']
                    evolved, _ = await evolve_pokemon(selected_pokemon)
                    if evolved:
                        await message.channel.send(
                            f"✨ What? {old_name.capitalize()} is evolving!\n"
                            f"🎊 Your {old_name.capitalize()} evolved into **{selected_pokemon['name'].capitalize()}**!"
                        )

@bot.command()
async def catch(ctx):
    """Attempts to catch the spawned pokemon."""
    channel_id = str(ctx.channel.id)
    user_id = str(ctx.author.id)

    if channel_id not in spawned_pokemon:
        await ctx.send("❌ There's no wild Pokémon here!")
        return

    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("❌ You need to start your journey first! Use `!start`")
        return

    if user_id in spawned_pokemon[channel_id]["failed_catchers"]:
        await ctx.send("❌ You already failed to catch this Pokémon! Let others try.")
        return

    spawn_data = spawned_pokemon[channel_id]
    pokemon_name = spawn_data["name"]
    level = spawn_data["level"]
    rarity = spawn_data["rarity"]

    required_ball = get_required_ball(rarity)

    if user_id not in user_balance:
        init_user_balance(user_id)

    if user_balance[user_id]["pokeballs"][required_ball] <= 0:
        ball_names = {"pokeball": "Poké Ball", "greatball": "Great Ball", "ultraball": "Ultra Ball", "masterball": "Master Ball"}
        await ctx.send(f"❌ You need a **{ball_names[required_ball]}** to catch this Pokémon!")
        return

    user_balance[user_id]["pokeballs"][required_ball] -= 1

    catch_rate = get_catch_rate(rarity)
    roll = random.randint(1, 100)

    if roll <= catch_rate:
        ivs = generate_ivs()
        stats = calculate_actual_stats(pokemon_name, level, ivs)
        moves = get_moves_for_level(pokemon_name, level)

        new_pokemon = {
            "name": pokemon_name,
            "level": level,
            "xp": 0,
            "gender": random.choice(["Male", "Female"]),
            "nature": random.choice(["Adamant", "Bold", "Brave", "Calm", "Gentle", "Hardy", "Jolly", "Modest", "Quiet", "Timid"]),
            "ivs": ivs,
            "stats": stats,
            "current_hp": stats["HP"],
            "moves": moves[:4]
        }

        user_data[user_id]["pokemons"].append(new_pokemon)

        iv_percent = sum(ivs.values()) / (31 * 6) * 100

        embed = discord.Embed(
            title="🎉 Gotcha!",
            description=f"**{ctx.author.display_name}** caught a **{pokemon_name.capitalize()}**!",
            color=0xFFD700
        )

        poke_image = pokedex_data.get(pokemon_name, {}).get('image_url')
        if poke_image:
            embed.set_thumbnail(url=poke_image)

        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Nature", value=f"**{new_pokemon['nature']}**", inline=True)
        embed.add_field(name="IV%", value=f"**{iv_percent:.1f}%**", inline=True)

        await ctx.send(embed=embed)

        del spawned_pokemon[channel_id]

    else:
        spawn_data["attempts"] += 1
        spawn_data["failed_catchers"].add(user_id)

        if spawn_data["attempts"] >= MAX_CATCH_ATTEMPTS:
            await ctx.send(f"💨 The wild {pokemon_name.capitalize()} ran away after {MAX_CATCH_ATTEMPTS} failed attempts!")
            del spawned_pokemon[channel_id]
        else:
            attempts_left = MAX_CATCH_ATTEMPTS - spawn_data["attempts"]
            await ctx.send(f"❌ {ctx.author.mention} failed to catch it! **{attempts_left}** attempts remaining for others.")

@bot.command()
async def evolve(ctx):
    """Manually evolve your selected pokemon if it's ready."""
    user_id = str(ctx.author.id)

    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("❌ You haven't started your journey yet!")
        return

    player_data = user_data[user_id]
    selected_pokemon = player_data["pokemons"][player_data["selected_pokemon_index"]]

    can_evo, new_form = can_evolve(selected_pokemon)

    if not can_evo:
        if selected_pokemon["name"] not in EVOLUTION_DATA:
            await ctx.send(f"❌ {selected_pokemon['name'].capitalize()} cannot evolve!")
        else:
            required_level = EVOLUTION_DATA[selected_pokemon["name"]]["level"]
            await ctx.send(f"❌ {selected_pokemon['name'].capitalize()} can evolve at level {required_level}! (Current: {selected_pokemon['level']})")
        return

    old_name = selected_pokemon['name']
    evolved, _ = await evolve_pokemon(selected_pokemon)

    if evolved:
        embed = discord.Embed(
            title="✨ Evolution!",
            description=f"Your **{old_name.capitalize()}** evolved into **{selected_pokemon['name'].capitalize()}**!",
            color=0xFFD700
        )

        poke_image = pokedex_data.get(selected_pokemon['name'], {}).get('image_url')
        if poke_image:
            embed.set_image(url=poke_image)

        embed.add_field(name="New Stats", value="\n".join([f"**{stat}:** {val}" for stat, val in selected_pokemon['stats'].items()]), inline=False)

        await ctx.send(embed=embed)

@bot.command()
async def learn(ctx, *, move_name: str = None):
    """Learn a new move or view available moves."""
    user_id = str(ctx.author.id)

    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("❌ You haven't started your journey yet!")
        return

    player_data = user_data[user_id]
    selected_pokemon = player_data["pokemons"][player_data["selected_pokemon_index"]]

    all_moves = pokemon_data.get(selected_pokemon["name"], {}).get("moves", [])
    current_moves = selected_pokemon.get("moves", [])

    if not move_name:
        available = [m for m in all_moves if m.lower() not in [cm.lower() for cm in current_moves]]

        embed = discord.Embed(
            title=f"📚 Moves for {selected_pokemon['name'].capitalize()}",
            description=f"Level {selected_pokemon['level']}",
            color=0x3B88C3
        )

        embed.add_field(
            name="Current Moves",
            value="\n".join([f"• **{m.title()}**" for m in current_moves]) if current_moves else "None",
            inline=False
        )

        if available:
            available_display = "\n".join([f"• {m.title()}" for m in available[:10]])
            if len(available) > 10:
                available_display += f"\n... and {len(available) - 10} more"

            embed.add_field(
                name="Available Moves",
                value=available_display,
                inline=False
            )

        embed.set_footer(text=f"Use !learn <move name> to learn a new move")

        await ctx.send(embed=embed)
        return

    move_name_normalized = move_name.lower().replace(" ", "-")

    if move_name_normalized not in [m.lower().replace(" ", "-") for m in all_moves]:
        await ctx.send(f"❌ {selected_pokemon['name'].capitalize()} cannot learn {move_name.title()}!")
        return

    if move_name_normalized in [m.lower().replace(" ", "-") for m in current_moves]:
        await ctx.send(f"❌ {selected_pokemon['name'].capitalize()} already knows {move_name.title()}!")
        return

    if len(current_moves) >= 4:
        moves_list = "\n".join([f"{i+1}. **{m.title()}**" for i, m in enumerate(current_moves)])
        await ctx.send(
            f"{selected_pokemon['name'].capitalize()} can only know 4 moves!\n\n"
            f"Current moves:\n{moves_list}\n\n"
            f"Reply with the number (1-4) of the move to replace, or `cancel` to cancel."
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and (m.content.isdigit() or m.content.lower() == "cancel")

        try:
            msg = await bot.wait_for('message', check=check, timeout=30)

            if msg.content.lower() == "cancel":
                await ctx.send("Cancelled move learning.")
                return

            slot = int(msg.content) - 1
            if slot < 0 or slot >= 4:
                await ctx.send("❌ Invalid slot number!")
                return

            old_move = current_moves[slot]
            current_moves[slot] = move_name

            await ctx.send(f"✅ {selected_pokemon['name'].capitalize()} forgot **{old_move.title()}** and learned **{move_name.title()}**!")

        except asyncio.TimeoutError:
            await ctx.send("⏱️ Move learning timed out.")
            return
    else:
        current_moves.append(move_name)
        await ctx.send(f"✅ {selected_pokemon['name'].capitalize()} learned **{move_name.title()}**!")

@bot.command()
@commands.has_permissions(administrator=True)
async def forcespawn(ctx, pokemon_name: str = None, level: int = None):
    """Force spawn a specific pokemon (admin only)."""
    if pokemon_name:
        pokemon_name = pokemon_name.lower()
        if pokemon_name not in pokemon_data:
            await ctx.send(f"❌ Pokemon '{pokemon_name}' not found!")
            return
    else:
        pokemon_name = spawn_random_pokemon()

    if not level:
        level = random.randint(1, 30)

    # Override spawn system
    channel_id = str(ctx.channel.id)
    rarity = get_pokemon_rarity(pokemon_name)

    spawned_pokemon[channel_id] = {
        "name": pokemon_name,
        "level": level,
        "rarity": rarity,
        "attempts": 0,
        "failed_catchers": set()
    }

    await spawn_pokemon_in_channel(ctx.channel)


@bot.command()
async def spawnrate(ctx):
    """Shows spawn information for current channel."""
    channel_id = str(ctx.channel.id)

    if channel_id not in spawn_tracker:
        await ctx.send("No spawn data for this channel yet!")
        return

    messages = spawn_tracker[channel_id]["messages"]
    guild_id = str(ctx.guild.id)
    active_count = len(active_users.get(guild_id, {}))
    threshold = SPAWN_ACTIVE_MESSAGES if active_count >= SPAWN_ACTIVE_THRESHOLD else SPAWN_BASE_MESSAGES

    embed = discord.Embed(title="📊 Spawn Info", color=0x00AAFF)
    embed.add_field(name="Messages Since Last Spawn", value=f"{messages}/{threshold}", inline=True)
    embed.add_field(name="Active Users", value=str(active_count), inline=True)
    embed.add_field(name="Spawned Pokemon", value="Yes" if channel_id in spawned_pokemon else "No", inline=True)

    await ctx.send(embed=embed)



# --- Looping Tasks ---
@tasks.loop(seconds=SAVE_INTERVAL_SECONDS)
async def save_user_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=4)

    with open(USER_BALANCE_FILE, "w") as f:
        json.dump(user_balance, f, indent=4)

# --- Player Commands ---
@bot.command()
async def start(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_data and user_data[user_id].get("pokemons"):
        await ctx.send("You've already started your journey!")
    else:
        user_data[user_id] = {}
        init_user_balance(user_id)  # Initialize balance
        await ctx.send(
            "Welcome to the world of Pokémon! Please choose your starter by typing `!choose <pokemon>`\n"
            "(Options: bulbasaur, charmander, squirtle)"
        )


@bot.command()
async def choose(ctx, choice: str):
    user_id = str(ctx.author.id)
    choice = choice.lower()

    if user_id not in user_data:
        await ctx.send("Please start your journey first using `!start`.")
        return
    if user_data.get(user_id) and user_data[user_id].get("pokemons"):
        await ctx.send("You've already chosen your starter Pokémon!")
        return
    if choice not in pokemon_data or choice not in ["bulbasaur", "charmander", "squirtle"]:
        await ctx.send("Invalid choice! Please choose from: bulbasaur, charmander, squirtle")
        return

    starter_pokemon = create_pokemon(choice, level=5)
    user_data[user_id] = {
        "pokemons": [starter_pokemon],
        "selected_pokemon_index": 0,
        "items": {}
    }

    # Give starter bonus items
    if user_id in user_balance:
        user_balance[user_id]["pokecoins"] += 1000  # Bonus coins
        user_balance[user_id]["pokeballs"]["pokeball"] += 10  # Bonus Poké Balls

    await ctx.send(
        f"You chose **{choice.capitalize()}**! Your journey begins now!\n"
        f"🎁 **Starter Pack:** +1000 PokéCoins, +10 Poké Balls!"
    )
    await ctx.send("Check your balance with `!bal` and your team with `!team`.")

def init_user_balance(user_id: str):
    """Initializes balance for a new user."""
    if user_id not in user_balance:
        user_balance[user_id] = {
            "pokecoins": 5000,  # Starting money
            "evolution_stones": {
                "fire": 0,
                "water": 0,
                "thunder": 0,
                "leaf": 0,
                "moon": 0,
                "sun": 0,
                "shiny": 0,
                "dusk": 0,
                "dawn": 0,
                "ice": 0
            },
            "mega_stones": {
                "charizardite-x": 0,
                "charizardite-y": 0,
                "venusaurite": 0,
                "blastoisinite": 0,
                "gengarite": 0
            },
            "redeem_shards": {
                "pokegem": 0,
                "gold_card": 0
            },
            "pokeballs": {
                "pokeball": 50,      # Regular Poké Balls
                "greatball": 20,     # Great Balls
                "ultraball": 10,     # Ultra Balls
                "masterball": 0      # Master Balls (rare!)
            }
        }

# ============================================
# REPLACE YOUR !bal COMMAND WITH THIS
# ============================================

@bot.command()
async def bal(ctx):
    """Shows the user's balance and items with custom Pokéball emojis."""
    user_id = str(ctx.author.id)

    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("❌ You haven't started your journey yet! Use `!start` first.")
        return

    if user_id not in user_balance:
        init_user_balance(user_id)

    balance = user_balance[user_id]

    embed = discord.Embed(
        title="💰 Poké-Currency & Items",
        description=f"**{ctx.author.display_name}'s Balance**",
        color=0xFFD700
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)

    # Poké Coins (LEFT)
    embed.add_field(
        name="🪙 Poké Coins",
        value=f"💰 **{balance['pokecoins']:,}**",
        inline=True
    )

    # Redeem Card Shards (RIGHT)
    shards = balance['redeem_shards']
    shard_text = (
        f"💎 **{shards['pokegem']}/100** PokéGem Shards\n"
        f"🏆 **{shards['gold_card']}/100** Gold Card Shards"
    )
    embed.add_field(
        name="🎴 Redeem Card Shards",
        value=shard_text,
        inline=True
    )

    # Separator
    embed.add_field(
        name="\u200b",
        value="─────────────────────────────────────────────────────",
        inline=False
    )

    # Poké Balls with custom emojis
    balls = balance['pokeballs']

    # Option A: Using predefined emoji IDs
    ball_lines = [
        f"{POKEBALL_EMOJIS['pokeball']} x**{balls['pokeball']}** Poké Balls",
        f"{POKEBALL_EMOJIS['greatball']} x**{balls['greatball']}** Great Balls",
        f"{POKEBALL_EMOJIS['ultraball']} x**{balls['ultraball']}** Ultra Balls"
    ]

    if balls['masterball'] > 0:
        ball_lines.append(f"{POKEBALL_EMOJIS['masterball']} x**{balls['masterball']}** Master Balls")

    # Option B: Using auto-detection (if emojis are uploaded)
    # ball_lines = [
    #     f"{get_pokeball_emoji(bot, 'pokeball')} x**{balls['pokeball']}** Poké Balls",
    #     f"{get_pokeball_emoji(bot, 'greatball')} x**{balls['greatball']}** Great Balls",
    #     f"{get_pokeball_emoji(bot, 'ultraball')} x**{balls['ultraball']}** Ultra Balls"
    # ]

    embed.add_field(
        name="⚪ Poké Balls",
        value="\n".join(ball_lines),
        inline=False
    )

    # Bottom separator
    embed.add_field(
        name="\u200b",
        value="─────────────────────────────────────────────────────",
        inline=False
    )

    embed.set_footer(text=f"Requested by @{ctx.author.name} • Use !shop to buy items!")
    embed.timestamp = discord.utils.utcnow()

    await ctx.send(embed=embed)



@bot.command()
async def info(ctx, index: int = None):
    """
    Shows detailed info about a Pokémon.
    Usage: !info - Shows selected Pokémon
           !info 2 - Shows Pokémon at position 2
    """
    user_id = str(ctx.author.id)

    # Check if user has started
    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("❌ You haven't started your journey yet. Use `!start` and `!choose`.")
        return

    player_data = user_data[user_id]

    # Determine which Pokémon to show
    if index is None:
        # Show selected Pokémon
        poke_index = player_data["selected_pokemon_index"]
    else:
        # Show Pokémon at specified position
        poke_index = index - 1  # Convert to 0-based index

        if poke_index < 0 or poke_index >= len(player_data["pokemons"]):
            await ctx.send(f"❌ Invalid position! You have {len(player_data['pokemons'])} Pokémon. Use `!team` to see your team.")
            return

    poke = player_data["pokemons"][poke_index]

    # Calculate total IV percentage
    total_iv_percent = sum(poke["ivs"].values()) / (31 * 6) * 100

    # Get Pokémon types
    poke_types = pokemon_data.get(poke['name'], {}).get('types', ['Normal'])
    types_display = " | ".join(poke_types)

    # Choose embed color based on primary type
    type_colors = {
        "Normal": 0xA8A878, "Fire": 0xF08030, "Water": 0x6890F0,
        "Electric": 0xF8D030, "Grass": 0x78C850, "Ice": 0x98D8D8,
        "Fighting": 0xC03028, "Poison": 0xA040A0, "Ground": 0xE0C068,
        "Flying": 0xA890F0, "Psychic": 0xF85888, "Bug": 0xA8B820,
        "Rock": 0xB8A038, "Ghost": 0x705898, "Dragon": 0x7038F8,
        "Dark": 0x705848, "Steel": 0xB8B8D0, "Fairy": 0xEE99AC
    }
    embed_color = type_colors.get(poke_types[0], 0x000000)

    # Create embed with dark theme
    embed = discord.Embed(
        title=f"Level {poke['level']} {poke['name'].capitalize()}",
        description=f"**Type:** {types_display}",
        color=embed_color
    )

    # Add Pokémon image
    poke_image = pokedex_data.get(poke['name'], {}).get('image_url')
    if poke_image:
        embed.set_thumbnail(url=poke_image)

    # ═══════════════════════════════════════
    # DETAILS SECTION
    # ═══════════════════════════════════════
    details = (
        f"**XP:** {poke['xp']}/100\n"
        f"**Nature:** {poke['nature']}\n"
        f"**Gender:** {poke['gender']}"
    )
    embed.add_field(name="📋 Details", value=details, inline=False)

    # ═══════════════════════════════════════
    # STATS WITH IVs (Combined Display)
    # ═══════════════════════════════════════
    stats_with_ivs = []
    for stat_key, stat_name in [
        ("HP", "HP"),
        ("Attack", "Attack"),
        ("Defense", "Defense"),
        ("Sp. Atk", "Sp. Atk"),
        ("Sp. Def", "Sp. Def"),
        ("Speed", "Speed")
    ]:
        stat_value = poke['stats'][stat_name]

        # Get corresponding IV
        iv_key = stat_name.lower().replace(". ", "_").replace(" ", "_")
        if iv_key == "sp_atk":
            iv_key = "sp_atk"
        elif iv_key == "sp_def":
            iv_key = "sp_def"

        iv_value = poke['ivs'].get(iv_key, 0)

        stats_with_ivs.append(f"**{stat_name}:** {stat_value} — IV: {iv_value}/31")

    embed.add_field(
        name="📊 Stats",
        value="\n".join(stats_with_ivs),
        inline=False
    )

    # ═══════════════════════════════════════
    # TOTAL IV PERCENTAGE
    # ═══════════════════════════════════════
    # Create visual bar for IV percentage
    iv_bar_length = 20
    iv_filled = int((total_iv_percent / 100) * iv_bar_length)
    iv_bar = "█" * iv_filled + "░" * (iv_bar_length - iv_filled)

    iv_color = "🟢" if total_iv_percent >= 80 else "🟡" if total_iv_percent >= 60 else "🔴"

    embed.add_field(
        name="💎 Total IV%",
        value=f"{iv_color} **{total_iv_percent:.2f}%**\n`{iv_bar}`",
        inline=False
    )

    # ═══════════════════════════════════════
    # MOVES SECTION
    # ═══════════════════════════════════════
    moves_display = ", ".join([f"**{move.title()}**" for move in poke['moves']])
    embed.add_field(
        name="⚔️ Moves",
        value=moves_display if moves_display else "No moves learned",
        inline=False
    )

    # ═══════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════
    footer_text = f"Pokémon #{poke_index + 1}/{len(player_data['pokemons'])}"
    if poke_index == player_data["selected_pokemon_index"]:
        footer_text += " • Currently Selected"

    embed.set_footer(text=footer_text)

    await ctx.send(embed=embed)

# -----------------------------------------------------------------
# PASTE THIS ENTIRE BLOCK INTO YOUR main.py
# (Replaces your existing !team command)
# -----------------------------------------------------------------

@bot.command()
async def team(ctx):
    """
    Shows a user's Pokémon collection in a clean, 3-column embed.
    (No 6-poke limit, no thumbnail)
    """
    user_id = str(ctx.author.id)

    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("❌ You don't have any Pokémon yet!")
        return

    player_data = user_data[user_id]
    all_pokemon = player_data["pokemons"]  # This is their full collection

    # Create embed
    embed = discord.Embed(
        title=f"🎒 {ctx.author.display_name}'s Pokémon Collection", # Changed title
        color=0x3BA55D  # Green
    )

    # --- CHANGE 2: Removed '/ 6' limit ---
    embed.set_author(
        name=f"Total Pokémon: {len(all_pokemon)}", # Changed from "Team Size: ... / 6"
        icon_url=ctx.author.display_avatar.url
    )

    # Type emoji mapping (using your existing map)
    type_emojis = {
        "Normal": "⚪", "Fire": "🔥", "Water": "💧", "Electric": "⚡", "Grass": "🌿",
        "Ice": "❄️", "Fighting": "🥊", "Poison": "☠️", "Ground": "🌍", "Flying": "🕊️",
        "Psychic": "🔮", "Bug": "🐛", "Rock": "🪨", "Ghost": "👻", "Dragon": "🐉",
        "Dark": "🌑", "Steel": "⚙️", "Fairy": "🧚"
    }

    # --- Build three columns as strings ---
    pokemon_col = ""
    type_col = ""
    info_col = ""

    # --- NEW: Limit to 25 to avoid embed breaking ---
    display_limit = 25 
    pokemon_to_display = all_pokemon[:display_limit]

    for i, poke in enumerate(pokemon_to_display):
        # Calculate IV
        iv_percent = sum(poke["ivs"].values()) / (31 * 6) * 100

        # Get types (supports dual-type)
        poke_types = pokemon_data.get(poke['name'], {}).get('types', ['Normal'])

        # Build type emoji display
        if len(poke_types) == 1:
            type_display = type_emojis.get(poke_types[0], "⚪")
        else:
            type1_emoji = type_emojis.get(poke_types[0], "⚪")
            type2_emoji = type_emojis.get(poke_types[1], "⚪")
            type_display = f"{type1_emoji}/{type2_emoji}"

        # Gender
        gender = "♂️" if poke['gender'] == "Male" else "♀️"

        # Selected marker
        selected_mark = "▶️ " if i == player_data["selected_pokemon_index"] else ""

        # 1. Pokémon Column
        pokemon_col += f"**{i+1}.** {selected_mark}**{poke['name'].capitalize()}** {gender}\n"

        # 2. Type Column
        type_col += f"{type_display}\n"

        # 3. Info Column
        info_col += f"Lvl. **{poke['level']}** | IV: **{iv_percent:.1f}%**\n"

    # --- Add the three columns as inline fields ---
    # \u200b is a zero-width space to prevent empty field errors if list is empty
    embed.add_field(name="Pokémon", value=pokemon_col + "\u200b", inline=True)
    embed.add_field(name="Type", value=type_col + "\u200b", inline=True)
    embed.add_field(name="Info", value=info_col + "\u200b", inline=True)

    # --- Footer ---
    selected_poke = all_pokemon[player_data["selected_pokemon_index"]]
    selected_name = selected_poke['name'].capitalize()
    selected_level = selected_poke['level']
    selected_hp = selected_poke['current_hp']
    max_hp = selected_poke['stats']['HP']

    footer_text = f"✨ Active: {selected_name} • Lvl {selected_level} • HP: {selected_hp}/{max_hp}\n" \
                  f"Use !select <number> to switch • !info <number> for details"

    # Add note if we are only showing a part of the collection
    if len(all_pokemon) > display_limit:
        footer_text += f"\n\nDisplaying {display_limit} of {len(all_pokemon)} Pokémon. (Page 1)"

    embed.set_footer(text=footer_text)

    # --- CHANGE 1: Removed thumbnail ---
    # The embed.set_thumbnail() lines have been deleted.

    await ctx.send(embed=embed)


@bot.command()
async def select(ctx, position: int):
    user_id = str(ctx.author.id)
    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("You don't have a team to select from!")
        return

    player_data = user_data[user_id]
    if 1 <= position <= len(player_data["pokemons"]):
        player_data["selected_pokemon_index"] = position - 1
        selected_poke_name = player_data['pokemons'][position - 1]['name'].capitalize()
        await ctx.send(f"You have selected your **{selected_poke_name}**!")
    else:
        await ctx.send("Invalid position number. Check `!team` to see your team.")

# --- Battle Commands ---
@bot.command()
async def battle(ctx, opponent: discord.Member):
    """Challenge another player to a battle."""
    challenger = ctx.author

    if challenger == opponent:
        await ctx.send("❌ You can't battle yourself!")
        return

    if ctx.channel.id in active_battles:
        await ctx.send("❌ There is already a battle happening in this channel!")
        return

    if str(challenger.id) not in user_data or not user_data[str(challenger.id)].get("pokemons"):
        await ctx.send(f"❌ {challenger.mention}, you need to start your journey first with `!start`.")
        return

    if str(opponent.id) not in user_data or not user_data[str(opponent.id)].get("pokemons"):
        await ctx.send(f"❌ {opponent.mention} has not started their journey yet!")
        return

    # Create pending battle
    active_battles[ctx.channel.id] = {
        "type": "pending",
        "challenger": challenger,
        "opponent": opponent
    }

    embed = discord.Embed(
        title="⚔️ Battle Challenge!",
        description=f"{opponent.mention}, you have been challenged to a battle by {challenger.mention}!",
        color=discord.Color.red()
    )
    embed.add_field(
        name="How to Accept",
        value="Type `!accept` to fight!\n*Make sure your DMs are open to receive move selections!*",
        inline=False
    )
    embed.set_footer(text="Battle will be cancelled after 60 seconds of no response.")

    await ctx.send(embed=embed)


@bot.command()
async def accept(ctx):
    """Accept a pending battle challenge."""
    if ctx.channel.id not in active_battles or active_battles[ctx.channel.id].get("type") != "pending":
        await ctx.send("❌ There are no pending battles to accept in this channel.")
        return

    pending_battle = active_battles[ctx.channel.id]
    if ctx.author != pending_battle["opponent"]:
        await ctx.send("❌ You are not the one being challenged!")
        return

    challenger = pending_battle["challenger"]
    opponent = pending_battle["opponent"]

    # Create battle instance
    battle_instance = Battle(challenger, opponent, ctx.channel)
    active_battles[ctx.channel.id] = battle_instance

    # Start the battle
    await ctx.send("🔥 **Battle Starting!** 🔥")
    await asyncio.sleep(1)
    await battle_instance.show_battle_status("The battle begins!")
    await asyncio.sleep(1)

    # Request first moves
    await battle_instance.request_moves()


# ============================================
# REMOVE OR UPDATE YOUR OLD !fight COMMAND
# The !fight command now works in DMs only during battles
# You can remove the channel-based !fight command or keep it as fallback
# ============================================

# Optional: Remove this old command if you had it
# @bot.command()
# async def fight(ctx, *, move_name: str):
#     # This is now handled in DMs


# ============================================
# FIX 1: UPDATED show_battle_status METHOD
# Find this method in your Battle class and REPLACE it completely
# ============================================

async def show_battle_status(self, message: str = ""):
    """Sends an embed with the current battle status to the channel."""
    embed = discord.Embed(
        title=f"⚔️ Battle: {self.challenger.display_name} vs {self.opponent.display_name}",
        description=message if message else "Choose your move!",
        color=discord.Color.blue()
    )

    # Challenger's Pokémon info
    cp = self.challenger_pokemon
    cp_name = cp['name'].capitalize()
    cp_types = " | ".join(pokemon_data.get(cp['name'], {}).get('types', ['Normal']))

    embed.add_field(
        name=f"{self.challenger.display_name}'s {cp_name} (Lv.{cp['level']})",
        value=f"**Type:** {cp_types}\n{self.get_hp_bar(cp['current_hp'], cp['stats']['HP'])}",
        inline=False
    )

    # Opponent's Pokémon info
    op = self.opponent_pokemon
    op_name = op['name'].capitalize()
    op_types = " | ".join(pokemon_data.get(op['name'], {}).get('types', ['Normal']))

    embed.add_field(
        name=f"{self.opponent.display_name}'s {op_name} (Lv.{op['level']})",
        value=f"**Type:** {op_types}\n{self.get_hp_bar(op['current_hp'], op['stats']['HP'])}",
        inline=False
    )

    # Add challenger's Pokémon image (thumbnail - top right)
    cp_image = pokedex_data.get(cp['name'], {}).get('image_url')
    if cp_image:
        embed.set_thumbnail(url=cp_image)

    # Add opponent's Pokémon image (main image - bottom)
    op_image = pokedex_data.get(op['name'], {}).get('image_url')
    if op_image:
        embed.set_image(url=op_image)

    embed.set_footer(text="Moves sent to DMs! You have 15 seconds to choose.")
    await self.channel.send(embed=embed)


# ============================================
# FIX 2: ADD game_over CHECK IN request_moves
# Find your request_moves method and UPDATE the beginning
# ============================================

async def request_moves(self):
    """Requests moves from both players via DM."""
    # Check if battle is already over (important for forfeit fix)
    if self.game_over:
        return False

    self.move_selection_active = True
    self.challenger_move = None
    self.opponent_move = None

    # Send move options to both players
    await self.show_battle_status("📨 Move selections sent to your DMs!")

    dm_sent_challenger = await self.send_move_choices_dm(self.challenger, self.challenger_pokemon)
    dm_sent_opponent = await self.send_move_choices_dm(self.opponent, self.opponent_pokemon)

    if not dm_sent_challenger or not dm_sent_opponent:
        await self.channel.send("❌ Battle cancelled due to DM issues.")
        if self.channel.id in active_battles:
            del active_battles[self.channel.id]
        return False

    # Wait 15 seconds for both players to choose
    await asyncio.sleep(15)

    # Check again if battle ended during the wait
    if self.game_over:
        return False

    self.move_selection_active = False

    # Process the turn
    await self.execute_turn()
    return True


# ============================================
# FIX 3: ADD game_over CHECK IN execute_turn
# Find your execute_turn method and UPDATE it
# ============================================

async def execute_turn(self):
    """Executes the turn after both players have selected moves."""

    # Check if battle is already over
    if self.game_over:
        return

    # Check if both players selected moves
    if self.challenger_move is None:
        await self.channel.send(f"⏱️ {self.challenger.mention} didn't select a move in time!")

    if self.opponent_move is None:
        await self.channel.send(f"⏱️ {self.opponent.mention} didn't select a move in time!")

    # If neither selected, end turn
    if self.challenger_move is None and self.opponent_move is None:
        await self.channel.send("💤 Both players passed! Requesting moves again...")
        await self.request_moves()
        return

    # Determine order based on speed (faster goes first)
    challenger_speed = self.challenger_pokemon['stats']['Speed']
    opponent_speed = self.opponent_pokemon['stats']['Speed']

    # Create attack order
    if challenger_speed > opponent_speed:
        first_attacker = self.challenger
        first_move = self.challenger_move
        second_attacker = self.opponent
        second_move = self.opponent_move
    elif opponent_speed > challenger_speed:
        first_attacker = self.opponent
        first_move = self.opponent_move
        second_attacker = self.challenger
        second_move = self.challenger_move
    else:
        # Same speed - random
        if random.choice([True, False]):
            first_attacker = self.challenger
            first_move = self.challenger_move
            second_attacker = self.opponent
            second_move = self.opponent_move
        else:
            first_attacker = self.opponent
            first_move = self.opponent_move
            second_attacker = self.challenger
            second_move = self.challenger_move

    # Execute first attack
    if first_move:
        fainted = await self.execute_attack(first_attacker, first_move)
        if fainted or self.game_over:
            return

    await asyncio.sleep(1)

    # Execute second attack
    if second_move:
        fainted = await self.execute_attack(second_attacker, second_move)
        if fainted or self.game_over:
            return

    # If battle still going, request next moves
    if not self.game_over:
        await asyncio.sleep(1.5)
        await self.request_moves()


# ============================================
# FIX 4: ADD game_over CHECK IN process_move_from_dm
# Find your process_move_from_dm method and UPDATE it
# ============================================

async def process_move_from_dm(self, player: discord.Member, move_name: str):
    """Processes a move selection from DM."""
    # Don't process moves if battle is over
    if self.game_over:
        await player.send("❌ This battle has already ended!")
        return False

    if not self.move_selection_active:
        await player.send("⏱️ Move selection is not currently active!")
        return False

    if player == self.challenger:
        if self.challenger_move is None:
            # Validate move
            if move_name.lower() in [m.lower() for m in self.challenger_pokemon["moves"]]:
                self.challenger_move = move_name
                await player.send(f"✅ You selected **{move_name.capitalize()}**!")
                return True
            else:
                await player.send(f"❌ Your {self.challenger_pokemon['name'].capitalize()} doesn't know that move!")
                return False
    elif player == self.opponent:
        if self.opponent_move is None:
            # Validate move
            if move_name.lower() in [m.lower() for m in self.opponent_pokemon["moves"]]:
                self.opponent_move = move_name
                await player.send(f"✅ You selected **{move_name.capitalize()}**!")
                return True
            else:
                await player.send(f"❌ Your {self.opponent_pokemon['name'].capitalize()} doesn't know that move!")
                return False
    return False


# ============================================
# FIX 5: COMPLETELY REPLACE YOUR !forfeit COMMAND
# Find @bot.command() async def forfeit and REPLACE THE ENTIRE THING
# ============================================

@bot.command()
async def forfeit(ctx):
    """Forfeit the current battle."""
    # Check if there's an active battle
    if ctx.channel.id not in active_battles:
        await ctx.send("❌ There's no battle to forfeit.")
        return

    battle_instance = active_battles[ctx.channel.id]

    # Check if it's a Battle object (not pending)
    if not isinstance(battle_instance, Battle):
        await ctx.send("❌ The battle hasn't started yet.")
        return

    # Determine winner and loser
    if ctx.author == battle_instance.challenger:
        winner = battle_instance.opponent
        loser = battle_instance.challenger
    elif ctx.author == battle_instance.opponent:
        winner = battle_instance.challenger
        loser = battle_instance.opponent
    else:
        await ctx.send("❌ You are not part of this battle.")
        return

    # IMPORTANT: Set game_over flag FIRST to stop all battle processes
    battle_instance.game_over = True
    battle_instance.move_selection_active = False

    # Send forfeit message
    embed = discord.Embed(
        title="🏳️ Battle Forfeited!",
        description=f"{loser.mention} has forfeited the match!",
        color=discord.Color.orange()
    )
    embed.add_field(
        name="Winner",
        value=f"🏆 {winner.mention} wins by forfeit!",
        inline=False
    )
    await ctx.send(embed=embed)

    # Clean up the battle
    if ctx.channel.id in active_battles:
        del active_battles[ctx.channel.id]

    # Notify both players in DM
    try:
        await loser.send(f"You forfeited the battle against {winner.display_name}.")
        await winner.send(f"🏆 {loser.display_name} forfeited! You win!")
    except:
        pass  # DMs might be closed

# === ADD THIS TO YOUR CONSTANTS SECTION (around line 15) ===
POKEDEX_DATA_FILE = "pokedex_data.json"

# === ADD THIS TO YOUR GLOBAL DATA STORES (around line 23) ===
pokedex_data = {}

# === UPDATE YOUR load_data() FUNCTION (around line 27) ===
def load_data():
    """Loads all necessary data from JSON files into memory."""
    global user_data, pokemon_data, moves_data, pokedex_data

    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(USER_DATA_FILE, "r") as f:
        try:
            user_data = json.load(f)
        except json.JSONDecodeError:
            user_data = {}

    with open(POKEMON_DATA_FILE, "r") as f:
        pokemon_data = json.load(f)

    with open(MOVES_DATA_FILE, "r") as f:
        moves_data = json.load(f)

    # Load Pokédex data
    with open(POKEDEX_DATA_FILE, "r") as f:
        pokedex_data = json.load(f)


# === ADD THIS COMMAND AFTER YOUR OTHER BOT COMMANDS (around line 260) ===

@bot.command()
async def dex(ctx, *, pokemon_name: str = None):
    """Shows detailed Pokédex information for a Pokémon."""

    if not pokemon_name:
        await ctx.send("Please specify a Pokémon! Usage: `!dex <pokemon_name>`")
        return

    pokemon_name = pokemon_name.lower()

    # Check if Pokémon exists in Pokédex
    if pokemon_name not in pokedex_data:
        await ctx.send(f"❌ Pokémon '{pokemon_name}' not found in the Pokédex!")
        return

    poke = pokedex_data[pokemon_name]

    # Type color mapping
    type_colors = {
        "grass": 0x78C850,
        "fire": 0xF08030,
        "water": 0x6890F0,
        "normal": 0xA8A878,
        "electric": 0xF8D030,
        "ice": 0x98D8D8,
        "fighting": 0xC03028,
        "poison": 0xA040A0,
        "ground": 0xE0C068,
        "flying": 0xA890F0,
        "psychic": 0xF85888,
        "bug": 0xA8B820,
        "rock": 0xB8A038,
        "ghost": 0x705898,
        "dragon": 0x7038F8,
        "dark": 0x705848,
        "steel": 0xB8B8D0,
        "fairy": 0xEE99AC
    }

    # Get primary type color
    primary_type = poke["types"][0].lower()
    embed_color = type_colors.get(primary_type, 0x000000)

    # Create embed
    embed = discord.Embed(
        title=f"#{poke['number']:03d} - {pokemon_name.capitalize()}",
        description=poke["description"],
        color=embed_color
    )

    # Add Pokémon image
    embed.set_thumbnail(url=poke["image_url"])

    # Types
    type_str = " | ".join([f"**{t.capitalize()}**" for t in poke["types"]])
    embed.add_field(name="Type", value=type_str, inline=True)

    # Height and Weight
    embed.add_field(name="Height", value=poke["height"], inline=True)
    embed.add_field(name="Weight", value=poke["weight"], inline=True)

    # Abilities
    abilities_str = " / ".join(poke["abilities"])
    embed.add_field(name="Abilities", value=abilities_str, inline=False)

    # Base Stats with progress bars
    stat_display = []
    base_stats = poke["base_stats"]

    stat_names = {
        "hp": "HP",
        "attack": "Attack",
        "defense": "Defense",
        "sp_atk": "Sp. Atk",
        "sp_def": "Sp. Def",
        "speed": "Speed"
    }

    for stat_key, stat_name in stat_names.items():
        stat_value = base_stats[stat_key]

        # Create progress bar (max 150 for visualization)
        bar_length = 15
        filled = min(int((stat_value / 150) * bar_length), bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        stat_display.append(f"**{stat_name}**: {stat_value:3d} `{bar}`")

    # Total base stats
    total_stats = sum(base_stats.values())
    stat_display.append(f"\n**Total**: {total_stats}")

    embed.add_field(
        name="📊 Base Stats",
        value="\n".join(stat_display),
        inline=False
    )

    # Evolution chain
    if poke["evolution"]:
        embed.add_field(name="🔄 Evolution", value=poke["evolution"], inline=False)

    # Category
    embed.add_field(name="Category", value=poke["category"], inline=True)

    # Gender ratio
    if poke["gender_ratio"]:
        embed.add_field(name="Gender Ratio", value=poke["gender_ratio"], inline=True)

    embed.set_footer(text=f"Generation {poke['generation']} • Use !catch to find this Pokémon!")

    await ctx.send(embed=embed)

# Add this command after your !dex command (around line 280)

@bot.command()
async def move(ctx, *, move_name: str = None):
    """Shows detailed information about a Pokémon move."""

    if not move_name:
        await ctx.send("Please specify a move! Usage: `!move <move_name>`")
        return

    move_name = move_name.lower().replace(" ", "-")  # Handle spaces

    # Check if move exists
    if move_name not in moves_data:
        await ctx.send(f"❌ Move '{move_name}' not found in the database!")
        return

    move = moves_data[move_name]

    # Type color mapping
    type_colors = {
        "normal": 0xA8A878,
        "fire": 0xF08030,
        "water": 0x6890F0,
        "electric": 0xF8D030,
        "grass": 0x78C850,
        "ice": 0x98D8D8,
        "fighting": 0xC03028,
        "poison": 0xA040A0,
        "ground": 0xE0C068,
        "flying": 0xA890F0,
        "psychic": 0xF85888,
        "bug": 0xA8B820,
        "rock": 0xB8A038,
        "ghost": 0x705898,
        "dragon": 0x7038F8,
        "dark": 0x705848,
        "steel": 0xB8B8D0,
        "fairy": 0xEE99AC
    }

    move_type = move.get("type", "normal").lower()
    embed_color = type_colors.get(move_type, 0x000000)

    # Create embed
    embed = discord.Embed(
        title=f"⚡ {move_name.replace('-', ' ').title()}",
        description=move.get("effect", "No description available."),
        color=embed_color
    )

    # Type and Category
    move_type_display = move.get("type", "Normal").capitalize()
    category = move.get("category", "physical").capitalize()

    # Category emoji
    category_emoji = {
        "physical": "💥",
        "special": "✨",
        "status": "🔄"
    }

    embed.add_field(
        name="Type",
        value=f"**{move_type_display}**",
        inline=True
    )

    embed.add_field(
        name="Category",
        value=f"{category_emoji.get(category.lower(), '❓')} **{category}**",
        inline=True
    )

    # Power
    power = move.get("power", 0)
    power_display = "—" if power == 0 else str(power)
    embed.add_field(
        name="Power",
        value=f"**{power_display}**",
        inline=True
    )

    # Accuracy
    accuracy = move.get("accuracy", 100)
    embed.add_field(
        name="Accuracy",
        value=f"**{accuracy}%**",
        inline=True
    )

    # PP (Power Points)
    pp = move.get("pp", 0)
    embed.add_field(
        name="PP",
        value=f"**{pp}**",
        inline=True
    )

    # Add a spacer for better layout
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # Show which of user's Pokémon can learn this move (if user has started)
    user_id = str(ctx.author.id)
    if user_id in user_data and user_data[user_id].get("pokemons"):
        learners = []
        for poke in user_data[user_id]["pokemons"]:
            if move_name in [m.lower().replace(" ", "-") for m in poke.get("moves", [])]:
                learners.append(poke["name"].capitalize())

        if learners:
            embed.add_field(
                name="📚 Your Pokémon that know this move",
                value=", ".join(learners),
                inline=False
            )

    embed.set_footer(text="Use !fight <move> in battle to use this move!")

    await ctx.send(embed=embed)


# BONUS: Add a !moves command to list all moves (optional)
@bot.command()
async def moves(ctx, filter_type: str = None):
    """Lists all available moves, optionally filtered by type."""

    if filter_type:
        filter_type = filter_type.lower()
        filtered_moves = {name: data for name, data in moves_data.items() 
                         if data.get("type", "").lower() == filter_type}

        if not filtered_moves:
            await ctx.send(f"No moves found for type '{filter_type}'!")
            return

        title = f"{filter_type.capitalize()}-type Moves"
        moves_list = filtered_moves
    else:
        title = "All Available Moves"
        moves_list = moves_data

    # Create paginated list (show first 50)
    move_names = sorted(list(moves_list.keys())[:50])

    embed = discord.Embed(
        title=title,
        description="\n".join([f"• {name.replace('-', ' ').title()}" for name in move_names]),
        color=discord.Color.blue()
    )

    if len(moves_list) > 50:
        embed.set_footer(text=f"Showing 50 of {len(moves_list)} moves. Use !move <name> for details.")
    else:
        embed.set_footer(text=f"Total: {len(moves_list)} moves. Use !move <name> for details.")

    await ctx.send(embed=embed)
    
# --- Run Bot ---
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: TOKEN not found in .env file.")



