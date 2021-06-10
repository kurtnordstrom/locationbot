#import bot_commmands
import discord
import re
import inspect
import sys
import sqlite3
from dotenv import dotenv_values

client = discord.Client()

COMMAND_PREFIX="+lb"

COMMAND_REGEX = None

RP_CATEGORY_NAME = ""
DB_CONN = None
DB_PATH = ""

MAX_CHANNEL_COUNT = 7

@client.event
async def on_ready():
    print(f"{client.user} logged in now")

@client.event
async def on_message(message):
    basic_message_stat_dump(message)
    await parse_command(message)
    #if message.content.startswith(COMMAND_PREFIX):
    #    await message.channel.send(f"Hello! {message.author}")

def basic_message_stat_dump(message):
    print(f"Got message: {message.content}")
    print(f"-> channel: {message.channel}")
    print(f"-> author: {message.author}")

async def parse_command(message):
    global COMMAND_REGEX
    command_string = message.content
    if not COMMAND_REGEX:
        COMMAND_REGEX = re.compile(re.escape(COMMAND_PREFIX) + r"\s+(?P<command>\S+)(\s+(?P<args>.+))?")
    result = re.match(COMMAND_REGEX, command_string)
    if not result:
        return
    command = result.group("command")
    args = result.group("args")
    print(f"Parsed command '{command}' with args '{args}'")
    if not command in COMMAND_DICT:
        await message.channel.send(f"{command} is not a valid command")
        return
    entry = COMMAND_DICT[command]
    func_name = entry["func"]
    members = inspect.getmembers(sys.modules[__name__])
    for member in members:
        func = None
        if member[0] == func_name:
            func = member[1]
        if func and inspect.isfunction(func):
            await func(message, args)
            return
    await message.channel.send("Function not defined")


COMMAND_DICT = {\
    "help" : {\
        "desc": "help: Show the bot commands",
        "func": "list_commands",
    },
    "locations" : {
        "desc": "locations [category]: List available locations for a"
                +" given category, or all if no category is provided",
                "func": "list_locations"
    },
    "addloc" : {
        "desc" : "addloc <category> \"<location name>\" \"<location desc>\" Add a new location to a given category",
        "func" : "add_location"
    },
    "editloc": {
        "desc" : "editloc <category> \"<location name>\" \"<location desc>\" Edit the desc of an existing location",
        "func" : None
    },
    "delloc": {
        "desc" : "delloc <category> \"<location name>\" Delete a location from a given category",
        "func" : None
    },
    "categories" : {
        "desc" : "categories: List existing categories for locations",
        "func" : "list_categories"
    },
    "addcat" : {
        "desc" : "addcat <category> Add a new category. Note that category names cannot contain spaces",
        "func" : "add_category"
    },
    "delcat" : {
        "desc" : "delcat <category> Delete an existing category. Only works if there are no locations with this category",
        "func" : None
    },
    "newloc" : {
        "desc" : "newloc <category> <location name> Opens a new RP location with the given location name",
        "func" : "make_new_location"
    },
    "reloc" : {
        "desc" : "reloc <category> <location name> Renames the current RP location to a new location name",
        "func" : "rename_location"
    }

}

async def list_commands(message, args):
    commands_list = []
    for key,value in COMMAND_DICT.items():
        commands_list.append(COMMAND_PREFIX + " " + value["desc"])
        commands_string = "\n".join(commands_list)
    await message.channel.send("These are the commands:\n" + "```" + commands_string + "```")


async def _make_new_location(message, args):
    guild = message.guild
    categories = guild.categories
    rp_category = None
    for category in categories:
        if category.name == RP_CATEGORY_NAME:
            rp_category = category
            break
    if not rp_category:
        await message.channel.send(f"Unable to locate the proper category! {RP_CATEGORY_NAME}")
        return
    channels = rp_category.channels
    await message.channel.send(f"There are currently {len(channels)} channels in the {RP_CATEGORY_NAME} category")

def get_non_colliding_name(channel_category, name, depth=0):
    if depth > 0:
        candidate_name = "%s-%s" % (name, depth)
    else:
        candidate_name = name
    channels = channel_category.channels
    match_found = False
    for channel in channels:
        if channel.name == candidate_name:
            match_found = True
            break
    if match_found:
        return get_non_colliding_name(channel_category, name, depth + 1)
    return candidate_name

def get_db_connection(path):
    conn = None
    try:
        conn = sqlite3.connect(path)
    except Exception as e:
        print("Error getting connection to db: %s" % e)
    return conn

def init_db(conn):
    sql_create_categories = \
    """CREATE TABLE IF NOT EXISTS location_categories (
        id integer PRIMARY KEY,
        name text NOT NULL,
        date_created text,
        creator text
    );"""

    sql_create_locations = \
    """CREATE TABLE IF NOT EXISTS locations (
        id integer PRIMARY KEY,
        location_category_id integer NOT NULL,
        name text NOT NULL,
        desc text,
        date_created text,
        creator text,
        FOREIGN KEY (location_category_id) REFERENCES location_categories (id)
    );"""

    init_list = [ sql_create_categories, sql_create_locations ]

    try:
        for init_sql in init_list:
            c = conn.cursor()
            c.execute(init_sql)
    except Exception as e:
        print("Error initializing tables: %s" % e)

def get_date():
    return "0000-00-00T00:00:00Z"

def sanitize_channel_name(name):
    if not name:
        return name
    name = name.strip().lower()
    #replace spaces with dashes
    name = re.sub(r"\s+", "-", name)
    #replace illegal chars with nothing
    name = re.sub(r"[^a-zA-Z0-9\s-]", "", name)
    return name

def get_channel_category(guild, category_name):
    channel_categories = guild.categories
    rp_channel_category = None
    for channel_category in channel_categories:
        if channel_category.name == category_name:
            rp_channel_category = channel_category
            break
    return rp_channel_category


def parse_one_word_two_string(str):
    pattern = r'(\S+)\s+"(.+)"\s+"(.+)"'
    regex = re.compile(pattern)
    result = regex.match(str)
    if not result:
        return None
    return ( result.group(1), result.group(2), result.group(3) )

def get_category_by_name(conn, category_name):
    query_sql = """SELECT * from location_categories WHERE name = :name"""
    c = conn.cursor()
    c.execute(query_sql, {"name" : category_name})
    row = c.fetchone()
    return row

def get_location(conn, category_id, name):
    query_sql = """SELECT * from locations WHERE name = :name AND location_category_id = :category_id"""
    c = conn.cursor()
    c.execute(query_sql, { "name" : name, "category_id" : category_id })
    row = c.fetchone()
    return row

def get_location_catname(conn, category, name):
    catrow = get_category_by_name(conn, category)
    if not catrow:
        return None
    return get_location(conn, catrow[0], name)

def insert_category(conn, category_name, creator):
    insert_sql = """INSERT INTO location_categories(name, date_created, creator) VALUES (:name,:date,:creator)"""
    if get_category_by_name(conn, category_name):
        print(f"Category {category_name} already exists")
        return
    c = conn.cursor()
    c.execute(insert_sql, { "name": category_name, "date" : get_date(), "creator": creator })
    conn.commit()

def insert_location(conn, category_id, name, desc, creator):
    insert_sql = """
    INSERT INTO locations(location_category_id, name, desc, date_created, creator)
    VALUES(:category_id, :name, :desc, :date, :creator)"""
    c = conn.cursor()
    c.execute(insert_sql, { "category_id": category_id, "name" : name, "desc": desc,\
            "date" : get_date(), "creator" : creator })
    conn.commit()

def get_categories(conn):
    query_sql = """SELECT name from location_categories"""
    c = conn.cursor()
    c.execute(query_sql)
    output_list = []
    row = c.fetchone()
    while row:
        output_list.append(row[0])
        row = c.fetchone()
    return ','.join(output_list)

def get_locations(conn, category_name=None):
    query_sql = \
        """SELECT locations.name, locations.desc, locations.date_created, locations.creator, 
        locations.location_category_id, location_categories.name
        FROM locations 
        INNER JOIN location_categories ON locations.location_category_id = location_categories.id
        """

    if category_name:
        query_sql = query_sql + """ WHERE location_categories.name = :cat_name """

    query_sql = query_sql + """ ORDER BY location_categories.name;"""

    c = conn.cursor()
    if not category_name:
        c.execute(query_sql)
    else:
        c.execute(query_sql, { "cat_name" : category_name })
    return c.fetchall()



    

async def list_categories(message, args):
    global DB_CONN
    if not DB_CONN:
        DB_CONN = get_db_connection(DB_PATH)
    category_output = get_categories(DB_CONN)
    await message.channel.send(f"Current categories are: {category_output}")

async def add_category(message, args):
    global DB_CONN
    if not DB_CONN:
        DB_CONN = get_db_connection(DB_PATH)
    if not args:
        await message.channel.send("You need to supply a category name")
        return
    if len(args.split()) > 1:
        await message.channel.send("Categories can only be single words")
        return
    category_name = args.strip()
    if get_category_by_name(DB_CONN, category_name):
        await message.channel.send("That category already exists")
        return
    insert_category(DB_CONN, category_name, message.author.name)
    await message.channel.send(f"Category {category_name} added")

async def add_location(message, args):
    global DB_CONN
    if not DB_CONN:
        DB_CONN = get_db_connection(DB_PATH)
    arg_list = parse_one_word_two_string(args)
    print(f"Got arg_list {arg_list}")
    if not arg_list or len(arg_list) != 3:
        await message.channel.send("Proper usage: "+ COMMAND_DICT["addloc"]["desc"])
        return
    sanitized_channel = sanitize_channel_name(arg_list[1])
    if len(sanitized_channel) > 99:
        await message.channel.send("Channel names need to be 100 chars or less")
        return
    category_row = get_category_by_name(DB_CONN, arg_list[0])
    if not category_row:
        await message.channel.send(f"Category {arg_list[0]} has not been defined. Please add it first.")
        return
    category_id = category_row[0] #id 
    location_row = get_location(DB_CONN, category_id, sanitized_channel)
    if location_row:
        await message.channel.send(f"There is already a location called '{sanitized_channel}' in the '{arg_list[0]}' category")
        return
    await message.channel.send(f"Adding location '{sanitized_channel}' to category '{arg_list[0]}' with description '{arg_list[2]}'")
    insert_location(DB_CONN, category_id, sanitized_channel, arg_list[2], message.author.name)

async def list_locations(message, args):
    global DB_CONN
    if not DB_CONN:
        DB_CONN = get_db_connection(DB_PATH)
    category = None
    if args:
        category = args.split(None,1)[0]
    rows = get_locations(DB_CONN, category)
    if not rows:
        await message.channel.send(f"No locations found")
        return
    outlist = []
    current_cat = None
    for row in rows:
        if current_cat != row[5]:
            current_cat = row[5]
            outlist.append(f"Category: {current_cat}")
        outlist.append(row[0])
    outstring = "\n".join(outlist)
    await message.channel.send(outstring)

async def make_new_location(message, args):
    global MAX_CHANNEL_COUNT
    global RP_CATEGORY_NAME
    global DB_CONN
    if not DB_CONN:
        DB_CONN = get_db_connection(DB_PATH)
    arg_list = None
    if args:
        arg_list = args.split()
    if not arg_list or len(arg_list) != 2:
        await message.channel.send(f"Proper usage: " + COMMAND_DICT['newloc']['desc'])
        return
    category_name = arg_list[0]
    location_name = arg_list[1]
    location_row = get_location_catname(DB_CONN, category_name, location_name)
    if not location_row:
        await message.channel.send(f"There is no location of that name for the given category")
        return
    rp_channel_category = None
    guild = message.guild
    channel_categories = guild.categories
    rp_channel_category = get_channel_category(guild, RP_CATEGORY_NAME)
    if not rp_channel_category:
        await message.channel.send(f"Unable to locate the proper category! {RP_CATEGORY_NAME}")
        return
    if len(rp_channel_category.channels) >= MAX_CHANNEL_COUNT:
        await message.channel.send(f"Max number of allowed RP channels already created. Try renaming an existing one not in use.")
        return
    non_colliding_name = get_non_colliding_name(rp_channel_category, location_name)
    await message.channel.send(f"Creating new RP channel: '{non_colliding_name}'")
    await rp_channel_category.create_text_channel(non_colliding_name)

async def rename_location(message, args):
    global DB_CONN
    if not DB_CONN:
        DB_CONN = get_db_connection(DB_PATH)
    arg_list = None
    if args:
        arg_list = args.split()
    if not arg_list or len(arg_list) != 2:
        await message.channel.send(f"Proper usage: " + COMMAND_DICT['reloc']['desc'])
        return
    category_name = arg_list[0]
    location_name = arg_list[1]
    location_row = get_location_catname(DB_CONN, category_name, location_name)
    if not location_row:
        await message.channel.send(f"There is no location of that name for the given category")
        return
    rp_channel_category = get_channel_category(message.guild, RP_CATEGORY_NAME)
    current_channel_category = message.channel.category
    if current_channel_category != rp_channel_category:
        await message.channel.send(f"Only channels in the {RP_CATEGORY_NAME} category may be reassigned")
        return
    non_colliding_name = get_non_colliding_name(rp_channel_category, location_name)
    await message.channel.send(f"```Location changed to {non_colliding_name}```")
    await message.channel.edit(name=non_colliding_name)



if __name__ == "__main__":
    config = dotenv_values(".env")
    TOKEN = config["TOKEN"]
    DB_PATH = config["DB_PATH"]
    RP_CATEGORY_NAME = config["RP_CATEGORY_NAME"]
    DB_CONN = get_db_connection(DB_PATH)
    if(DB_CONN):
        init_db(DB_CONN)
    client.run(TOKEN)


