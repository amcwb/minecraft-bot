from typing import Optional
import discord
from discord.ext.commands import Bot
from discord.ext.commands.context import Context
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from paginator import EmbedPaginatorSession
import math

load_dotenv()
client = MongoClient(os.environ.get("MONGO"))
db = client.minecraft
bot = Bot("!", description="A minecraft bot")


def location_to_embed(loc):
    embed = discord.Embed(
        title="#{} {}".format(loc["id"], loc["name"] or "No name"),
        description=loc["description"] or "No description",
    )
    embed.add_field(
        name="Position", value="{}, {}, {}".format(loc["x"], loc["y"], loc["z"])
    )
    embed.add_field(name="Added by", value="<@{}>".format(loc["added_by"]))

    if "screenshot_url" in loc:
        embed.set_image(url=loc["screenshot_url"])

    return embed


def get_highest_id():
    doc = db.locations.find_one({}, sort=[["id", -1]])
    return doc.get("id") if doc else 0


@bot.event
async def on_ready():
    print("Connected as {}".format(bot.user))


@bot.command("show-all", aliases=["show_all"])
async def show_all(ctx, by_me_only: bool = False):
    """
    Show all locations
    """
    # Get all
    embeds = list(
        map(
            location_to_embed,
            db.locations.find({"added_by": str(ctx.author.id)} if by_me_only else {}),
        )
    )
    if len(embeds) == 0:
        return await ctx.send("No locations added yet")

    await EmbedPaginatorSession(ctx, *embeds).run()

@bot.command("show", aliases=["see"])
async def show(ctx, id: int):
    """
    Show a location
    """
    # Get all
    location = db.locations.find_one(dict(id=id))
    if location is None:
        return await ctx.send("No locations with that ID found")

    await ctx.send(embed=location_to_embed(location))


@bot.command("near-me", aliases=["near_me"])
async def near_me(ctx, x: float, y_or_z: float, z_or_y: Optional[float]):
    # Figure out locations
    if z_or_y:
        y = y_or_z
        z = z_or_y
    else:
        z = y_or_z
        y = z_or_y

    distances = [500, 1000, 2000, 5000]
    max_dist = distances[-1]

    filt = {"y": {"$gt": y - max_dist, "$lt": y + max_dist}} if y is not None else {}
    locations = [
        *db.locations.find(
            {
                "x": {"$gt": x - max_dist, "$lt": x + max_dist},
                "z": {"$gt": z - max_dist, "$lt": z + max_dist},
                **filt,
            }
        )
    ]

    def _create_embed(loc):
        embed = location_to_embed(loc)
        embed.set_footer(text="{} blocks away from you".format(round(loc["dist"])))
        return embed

    # Sort by distance
    for loc in locations:
        loc["dist"] = math.sqrt((loc["x"] - x) ** 2 + (loc["z"] - z) ** 2)

    locations.sort(key=lambda loc: loc["dist"])

    embeds = map(_create_embed, locations)

    if len(list(embeds)) == 0:
        return await ctx.send("Nothing within 5000 blocks of you.")
    
    await EmbedPaginatorSession(ctx, *embeds).run()


@bot.command("add")
async def add(ctx: Context, x: float, y: float, z: float, *, name: str):
    """
    Add a location
    """
    id = get_highest_id() + 1
    screenshot_url = (
        ctx.message.attachments[0].url if len(ctx.message.attachments) > 0 else None
    )
    db.locations.insert_one(
        dict(
            x=x,
            y=y,
            z=z,
            name=name,
            id=id,
            added_by=str(ctx.author.id),
            screenshot_url=screenshot_url,
        )
    )

    await ctx.send("Added location #{}".format(id))


@bot.command("edit-description", aliases=["describe"])
async def edit_description(ctx, id: int, *, description: str):
    result = db.locations.update_one(
        {"id": id}, {"$set": dict(description=description)}
    )
    if result.matched_count == 0:
        return await ctx.send("No place found with that ID")

    await ctx.send("Description updated!")


@bot.command("edit-name", aliases=["name"])
async def edit_name(ctx, id: int, *, name: str):
    result = db.locations.update_one({"id": id}, {"$set": dict(name=name)})
    if result.matched_count == 0:
        return await ctx.send("No place found with that ID")

    await ctx.send("Name updated!")


@bot.command("edit-location", aliases=["locate"])
async def edit_location(ctx, id: int, x: float, y: float, z: float):
    result = db.locations.update_one({"id": id}, {"$set": dict(x=x, y=y, z=z)})
    if result.matched_count == 0:
        return await ctx.send("No place found with that ID")

    await ctx.send("Location updated!")


@bot.command("edit-screenshot", aliases=["screenshot"])
async def edit_screenshot(ctx, id: int):
    screenshot_url = (
        ctx.message.attachments[0].url if len(ctx.message.attachments) > 0 else None
    )

    result = db.locations.update_one(
        {"id": id},
        {"$set": dict(screenshot_url=screenshot_url)}
        if screenshot_url
        else {"$unset": dict(screenshot_url=1)},
    )
    if result.matched_count == 0:
        return await ctx.send("No place found with that ID")

    await ctx.send("Screenshot updated!")


@bot.event
async def on_command_error(ctx, error):
    await ctx.send("An error occured, please see log for more info")
    raise error


bot.run(os.environ.get("TOKEN"))
