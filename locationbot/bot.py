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
        "func": None
    },
    "addloc" : {
        "desc" : "addloc <category> \"<location name>\" \"<location desc>\" Add a new location to a given category",
        "func" : None
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
        "desc" : "newloc <category> \"<location name>\" Opens a new RP location with the given location name",
        "func" : "make_new_location"
    },
    "reloc" : {
        "desc" : "reloc <category> \"<location name>\" Renames the current RP location to a new location name",
        "func" : None
    }

}

async def list_commands(message, args):
    commands_list = []
    for key,value in COMMAND_DICT.items():
        commands_list.append(COMMAND_PREFIX + " " + value["desc"])
        commands_string = "\n".join(commands_list)
    await message.channel.send("These are the commands:\n" + "```" + commands_string + "```")


async def make_new_location(message, args):
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

def category_exists(conn, category_name):
    query_sql = """SELECT * from location_categories WHERE name = :name"""
    c = conn.cursor()
    c.execute(query_sql, {"name" : category_name})
    row = c.fetchone()
    if not row:
        return False
    return True

def insert_category(conn, category_name, creator):
    insert_sql = """INSERT INTO location_categories(name, date_created, creator) VALUES (:name,:date,:creator)"""
    if category_exists(conn, category_name):
        print(f"Category {category_name} already exists")
        return
    c = conn.cursor()
    c.execute(insert_sql, { "name": category_name, "date" : get_date(), "creator": creator })
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
    if category_exists(DB_CONN, category_name):
        await message.channel.send("That category already exists")
        return
    insert_category(DB_CONN, category_name, message.author.name)
    await message.channel.send(f"Category {category_name} added")


if __name__ == "__main__":
    config = dotenv_values(".env")
    TOKEN = config["TOKEN"]
    DB_PATH = config["DB_PATH"]
    RP_CATEGORY_NAME = config["RP_CATEGORY_NAME"]
    DB_CONN = get_db_connection(DB_PATH)
    if(DB_CONN):
        init_db(DB_CONN)
    client.run(TOKEN)


