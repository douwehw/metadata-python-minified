from datetime import datetime
import json
import exiftool
import os
import discord
import subprocess
import glob
import time
from discord.ext import commands
from typing import Union

date = datetime.now()

keywords_f = open("keywords.json", "r")
keywords: dict = json.load(keywords_f)
keywords_f.close()

ALLOWED_ROLES = {
    1214329003792662569,    # List mod test in test server
    782672303091613706,     # List Mod in CLHQ
    803369408436633601,     # Dev in CLHQ
}

def get_version() -> str:
    version = "";
    vf = open("bot_ver", "r")
    version = vf.readline()
    vf.close()
    return version

HELP_TEXT = f"""```Help
Thom Yorke v3.{get_version()}.{date.day}.{date.month}.{date.year}
========================================================================
Commands with a filled in box require List Mod.

[] -help
Shows this message.

[] -version
Outputs the current bot version

[] -clear
Clears the terminal of the bot, clears every odd day.

[] -meta
Get metadata info from a google drive link of raw footage.
Usage: -meta [drive link]

[x] -addflag
Add a flag to the list of metadata flags.
Usage: addflag [encoder] | [software]

[x] -removeflag - Remove keyword
Usage: removeflag [encoder]

[x] -flags
List all keywords and flags.
========================================================================
(ty m4rk & marcus)
```"""

def increment_version() -> int:
    version_f = open("bot_ver", "r")
    version = int(version_f.readline())
    version += 1
    version_f.close()
    version_f = open("bot_ver", "w")
    version_f.truncate()
    version_f.write(str(version))
    version_f.close()
    return version

async def update_keywords_json(new_dict: dict):
    keyw_f = open("keywords.json", "w")
    json.dump(new_dict, keyw_f)
    keyw_f.close()

def split_around(string: str, before, after):
    return string.split(before)[1].split(after)[0]


async def download_file(command, msg):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding="utf-8", errors="replace")

    start_time = time.time()
    while process.poll() is None:
        output = str(process.stdout.readline())
        if "100%" in output:                                                                                        # filter out any non-progress messages
            await msg.edit(content=f"Download progress (Finished): ```{output.strip().split(',')[0]}, 0MB/s]```")
        elif "%" in output and "0%" not in output and time.time() - start_time > 2:                                 # Example message: 4%|         | 1.57M/42.5M [00:00<00:02, 14.2MB/s]
            eta_text = split_around(output, "<", ",")                                                               # "00:02"
            if eta_text == "00:00":
                eta = "now"
            elif eta_text.count(":") == 0:
                eta = "unknown (possibly error occurred)"
            elif eta_text.count(":") == 1:
                mins, seconds = map(int, eta_text.split(":"))
                if mins > 0:
                    eta = f"{mins} minutes, {seconds} seconds"
                else:
                    eta = f"{seconds} seconds"
            else:
                hours, mins, seconds = map(int, eta_text.split(":"))                                                # probably will never show up
                eta = f"{hours} hours, {mins} minutes, {seconds} seconds"

            await msg.edit(content=f"Download progress (ETA is {eta}): ```{output.strip()}```")
            start_time = time.time()
        elif "error" in output.lower() or "fail" in output.lower():
            raise Exception("Error: " + output)

    print("video finished download")


# Download file from given Google Drive link and send download stats to channel
async def download_drive(drive_link: str, msg: discord.Message) -> None:
    if os.path.isfile("./gdrive.mp4"):                           # Check if the given link is from Google Drive.
        os.remove("./gdrive.mp4")

    print(f'Downloading {drive_link}')
    output: str = "gdrive.mp4"

    command = ["gdown", drive_link, f"-O", output, "--fuzzy"]   # Try to download the Google Drive file using gdown

    try:
        await download_file(command, msg)
    except Exception as e:
        await msg.edit(content="Error: " + str(e))


# Extract the metadata from the downloaded gdrive.mp4.
def meta_extraction() -> str:
    video = "./gdrive.mp4"
    exe = "./exiftool/exiftool"
    meta_buffer: Union[str, bytes] = ""
    metadata: str = ""

    delete_file_if_exists(path="./metadata.txt")                                                            # Check if metadata.txt already exists and delete if it does.

    with exiftool.ExifTool() as et:                                                                         # Using exiftool, we get the metadata and save it as metadata.txt.
        try:
            meta_buffer = et.execute("gdrive.mp4", "-api", "LargeFileSupport=1")                            # Load metadata into buffer

            metadata = str(meta_buffer)                                                                     # Load metadata as str into metadata variable

            fixed_metadata = "\n".join(line.rstrip() for line in metadata.split("\n") if len(line) > 4)     # remove any empty lines from metadata
            f = open("metadata.txt", "a")                                                                   # Write metadata to file
            f.write(fixed_metadata)
            f.close()
        except:
            print("metadata.txt does not exist.")

        cleanup(complete=False)                                                                             # We clean up the gdrive.mp4 as we don't need it anymore.
        return metadata


# Clean up the gdrive.mp4 and/or metadata.txt
def cleanup(complete: bool):
    delete_file_if_exists(path="./gdrive.mp4")          # Always try to delete the gdrive.mp4

    if complete:                                        # If the parameter for a compelete cleanup is true, we remove the metadata.txt as well.
        delete_file_if_exists(path="./metadata.txt")


# Check if a file exists and delete it if it does.
def delete_file_if_exists(path: str) -> None:
    if os.path.isfile(path):                            # Check if the file exists.
        os.remove(path)


# Check the metadata for flags
def validate_metadata(metadata) -> str:
    result: str = "> no identifiable flags found in metadata"
    for flag, software in json.loads(json.dumps(keywords)).items():     # Iterate over all the metadata flags
        if flag in metadata:
            result = f"> best guess for video origin: **{software}**"   # If the metadata contains one of the flags, print it out
            break
    return result

def clear_output():
    if (date.day % 2 == 0):
        subprocess.Popen("clear")


# Default Discord.py jargon
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="-", intents=intents)
bot.help_command = None                                     # Add our own help command later because discord.py is stinky

async def check_perms(ctx: commands.Context):
    for ROLE in ALLOWED_ROLES:
        if ROLE in map(lambda role: role.id, ctx.author.roles):
            return True

    await ctx.send("You don't have permissions for this command, you need List Mod role")
    return False

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user} on version {increment_version()}")

# use cmd(ctx, *, arg) here instead of cmd(ctx, arg) to get full param(s) of command easily
# example: =cmd skibidi! toilet! -> arg = "skibidi! toilet!"
@bot.command()
async def meta(ctx: commands.Context, *, arg):
    processing_msg = await ctx.send("Downloading video...")
    await download_drive(arg, processing_msg)                                   # Downloading
    metadata: str = "> you are not supposed to see this"
    metadata = meta_extraction()                                                # Loading metadata
    result = validate_metadata(metadata)
    await processing_msg.reply(result, file=discord.File(r"./metadata.txt"))    # Send results

    for file in glob.glob("gdrive*"):
        os.remove(file)
    cleanup(True)
    clear_output()

@bot.command()
async def addflag(ctx: commands.Context, *, arg):
    global keywords
    if not await check_perms(ctx): return
    key, val = arg.split("|")
    key, val = key.rstrip(), val.lstrip()       # get rid of spaces before and after pipe
    buffer_dict: dict = {key: val}
    buffer_dict.update(keywords)
    keywords = buffer_dict
    await update_keywords_json(buffer_dict)
    await ctx.send(f"Updated: `{key}` -> `{val}`")


@bot.command()
async def removeflag(ctx: commands.Context, *, arg):
    if not await check_perms(ctx): return
    try:
        keywords.pop(arg.rstrip().lstrip())
    except KeyError:
        await ctx.send("Keyword/flag does not exist.")
    else:
        await update_keywords_json(keywords)
        await ctx.send(f"Removed: `{arg}`")

@bot.command()
async def flags(ctx: commands.Context):
    if not await check_perms(ctx): return
    f = open("temp_lflags.txt", "w")                # Write to a temp file in case the actual flags list is too large for discord's liking
    for k in keywords.keys():
        f.write(f"{k}: {keywords[k]}\n")
    f.close()
    await ctx.send("Current keyword/flag list:", file=discord.File("temp_lflags.txt"))
    os.remove("temp_lflags.txt")

@bot.command()
async def clear(ctx: commands.Context):
    subprocess.Popen("clear")

@bot.command()
async def help(ctx: commands.Context):
    await ctx.send(HELP_TEXT)

@bot.command()
async def version(ctx: commands.Context):
    await ctx.send(f'Bot running on version v3.{get_version()}.{date.day}.{date.month}.{date.year - 2000}.{date.hour}.{date.minute}.{date.second}.{date.microsecond}')

@bot.command()
async def say(ctx: commands.Context):
    if not await check_perms(ctx): return
    message = ctx.message.content.split("say ")
    await ctx.send(message[1])

# YOM THORKE
# bot.run("Not leaking Bot tokens")

# THOM YORKE
bot.run("Not leaking Bot tokens")