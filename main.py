import discord
from discord.ext import commands, tasks
import os
import json
import random
from dotenv import load_dotenv
from keep_alive import keep_alive
import asyncio


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
SAVE_INTERVAL_SECONDS = 60
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

# --- Global Data Stores ---
user_data = {}
pokemon_data = {}
moves_data = {}
active_battles = {} # Key: channel.id, Value: Battle object

# --- Helper Functions ---
def load_data():
    """Loads all necessary data from JSON files into memory."""
    global user_data, pokemon_data, moves_data

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

        # Add both Pokémon images as thumbnails (side by side effect)
        cp_image = pokedex_data.get(cp['name'], {}).get('image_url')
        if cp_image:
            embed.set_thumbnail(url=cp_image)

        # Use author image for opponent instead of main image (keeps it smaller)
        op_image = pokedex_data.get(op['name'], {}).get('image_url')
        if op_image:
            embed.set_author(
                name=f"{op_name}",
                icon_url=op_image
            )

        embed.set_footer(text="Moves sent to DMs! You have 10 seconds to choose.")
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
        # Check if user is in an active battle
        for channel_id, battle in active_battles.items():
            if isinstance(battle, Battle):
                if message.author in [battle.challenger, battle.opponent]:
                    # Check if message is a fight command in DM
                    if message.content.startswith("!fight "):
                        move_name = message.content[7:].strip()
                        await battle.process_move_from_dm(message.author, move_name)
                    return

    # XP gain system (only in server channels, not DMs)
    if not isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        if user_id in user_data and user_data[user_id].get("pokemons"):
            player_data = user_data[user_id]
            if 0 <= player_data["selected_pokemon_index"] < len(player_data["pokemons"]):
                selected_pokemon = player_data["pokemons"][player_data["selected_pokemon_index"]]

                selected_pokemon["xp"] += 5
                if selected_pokemon["xp"] >= 100:
                    selected_pokemon["xp"] -= 100
                    selected_pokemon["level"] += 1
                    selected_pokemon["stats"] = calculate_actual_stats(
                        selected_pokemon["name"], 
                        selected_pokemon["level"], 
                        selected_pokemon["ivs"]
                    )
                    selected_pokemon["current_hp"] = selected_pokemon["stats"]["HP"]
                    await message.channel.send(
                        f"🎉 Congrats {message.author.mention}! Your {selected_pokemon['name'].capitalize()} is now **Level {selected_pokemon['level']}**!"
                    )



# --- Looping Tasks ---
@tasks.loop(seconds=SAVE_INTERVAL_SECONDS)
async def save_user_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=4)

# --- Player Commands ---
@bot.command()
async def start(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_data and user_data[user_id].get("pokemons"):
        await ctx.send("You've already started your journey!")
    else:
        user_data[user_id] = {}
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
    await ctx.send(f"You chose **{choice.capitalize()}**! Your journey begins now!")
    await ctx.send("You can check your Pokémon's details with `!info` and your team with `!team`.")

@bot.command()
async def info(ctx):
    user_id = str(ctx.author.id)
    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("You haven't started your journey yet. Use `!start` and `!choose`.")
        return

    player_data = user_data[user_id]
    poke = player_data["pokemons"][player_data["selected_pokemon_index"]]
    total_iv_percent = sum(poke["ivs"].values()) / (31 * 6) * 100

    embed = discord.Embed(
        title=f"Level {poke['level']} {poke['name'].capitalize()}",
        description=f"**XP:** {poke['xp']}/100\n**Gender:** {poke['gender']}\n**Nature:** {poke['nature']}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Stats", value="\n".join(f"**{stat}:** {value}" for stat, value in poke['stats'].items()), inline=False)
    embed.add_field(name="IVs", value="\n".join(f"{stat.upper()}: {val}/31" for stat, val in poke['ivs'].items()), inline=False)
    embed.add_field(name="Total IV%", value=f"{total_iv_percent:.2f}%", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def team(ctx):
    user_id = str(ctx.author.id)
    if user_id not in user_data or not user_data[user_id].get("pokemons"):
        await ctx.send("You don't have any Pokémon in your team yet!")
        return

    player_data = user_data[user_id]
    embed = discord.Embed(title=f"{ctx.author.display_name}'s Team", color=discord.Color.green())

    for i, poke in enumerate(player_data["pokemons"]):
        iv_percent = sum(poke["ivs"].values()) / (31 * 6) * 100
        selected_marker = ">> " if i == player_data["selected_pokemon_index"] else ""
        embed.add_field(
            name=f"{selected_marker}{i+1}. {poke['name'].capitalize()} (Lvl {poke['level']})",
            value=f"HP: {poke['current_hp']}/{poke['stats']['HP']} | IV: {iv_percent:.2f}%",
            inline=False
        )
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



