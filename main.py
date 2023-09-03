import traceback
from config import config, write_config, global_vars
from validation import validate_port, validate_ip, validate_country
from monitoring import generate_embed, monitor_task, monitor_servers

from asyncio import TimeoutError, sleep
from interactions import Client, Intents, SlashContext, Task, IntervalTrigger, check, listen, slash_command
from interactions import Modal, ShortText, ParagraphText
from interactions import Embed, EmbedField
from interactions import StringSelectMenu, StringSelectOption
from interactions import Activity, ActivityType
from interactions.api.events import CommandError

token = ""
bot = Client(
    intents=Intents.DEFAULT  # , sync_interactions=True, delete_unused_application_cmds=True
)
global_vars["bot"] = bot


async def interactions_validate_role(ctx: SlashContext):
    roles = ctx.author.roles

    for role in roles:
        if role.id in config["admin_roles"]:
            return True

    await ctx.send("You do not have permission to use this command", delete_after=5, ephemeral=True)

    return False


async def component_validate_role(comp):
    return await interactions_validate_role(comp.ctx)


async def update_status():
    await bot.change_presence(
        activity=Activity(
            name=f"on {len(config['servers'])} servers",
            type=ActivityType.GAME,
        )
    )


@listen()
async def on_ready():
    print("Ready")

    await update_status()
    monitor_task.start()
    await monitor_servers()


@listen(CommandError, disable_default_listeners=True)
async def on_command_error(event: CommandError):
    traceback.print_exception(event.error)


@check(check=interactions_validate_role)
@slash_command(
    name="addserver",
    description="Add a server to the monitoring list",
    dm_permission=False,
)
async def add_server(ctx: SlashContext):
    modal = Modal(
        ShortText(label="Server IP", custom_id="ip", placeholder="10.20.30.40"),
        ShortText(label="Port", custom_id="port", placeholder="27015"),
        ShortText(label="Name", custom_id="name", placeholder="My Cool Server"),
        ShortText(label="Two-letter country code", custom_id="country", placeholder="us"),
        ParagraphText(label="Notes (one per line, K:V, optional)", custom_id="notes", required=False),
        title="Add Server",
    )

    await ctx.send_modal(modal=modal)
    modal_ctx = await ctx.bot.wait_for_modal(modal)

    notes = {}

    lines = modal_ctx.responses["notes"].split("\n")
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            notes[key.strip()] = value.strip()

    ip = modal_ctx.responses["ip"]
    port = -1
    try:
        port = int(modal_ctx.responses["port"])
    except ValueError:
        pass

    server = {
        "name": modal_ctx.responses["name"],
        "country": modal_ctx.responses["country"].lower(),
        "notes": notes
    }

    problems = []

    if not validate_ip(ip):
        problems.append("Invalid IP: " + ip)
    if not validate_port(port):
        problems.append("Invalid port: " + str(port))
    if not validate_country(server["country"]):
        problems.append("Invalid country: " + server["country"])
    if f"{ip}:{port}" in config["servers"]:
        problems.append("Server already in list: " + ip + ":" + str(port))

    if len(problems) > 0:
        await modal_ctx.send("Failed to add server:\n" + "\n".join(problems), delete_after=5, ephemeral=True)
    else:
        config["servers"][ip + ":" + str(port)] = server
        write_config()

        await modal_ctx.send("Server added successfully", delete_after=5, ephemeral=True)


@check(check=interactions_validate_role)
@slash_command(
    name="removeserver",
    description="Remove a server from the monitoring list",
    dm_permission=False,
)
async def remove_server(ctx: SlashContext):
    server_choices = []

    for ip_port, server in config["servers"].items():
        server_choices.append(StringSelectOption(label=server["name"], value=ip_port))

    if len(server_choices) == 0:
        await ctx.send("No available servers - add one with /addserver", delete_after=5, ephemeral=True)

        return

    components = StringSelectMenu(
        *server_choices,
        placeholder="Select servers to remove",
        min_values=1,
        max_values=len(server_choices)
    )

    msg = await ctx.send("Select a server to remove", components=components, ephemeral=True)

    used_component = await bot.wait_for_component(
        components=components,
        check=component_validate_role
    )

    servers_to_remove = used_component.ctx.values

    for server_to_remove in servers_to_remove:
        del config["servers"][server_to_remove]

    write_config()
    await ctx.edit(content="Servers removed successfully", components=[])
    await sleep(5)
    await ctx.delete(msg)


@check(check=interactions_validate_role)
@slash_command(
    name="listservers", description="List all servers being monitored"
)
async def list_servers(ctx: SlashContext):
    if len(config["servers"]) == 0:
        await ctx.send("No servers to list", delete_after=5, ephemeral=True)

        return

    embed = Embed(title="Servers")
    fields = []

    for ip_port, server in config["servers"].items():
        fields.append(
            EmbedField(
                name=ip_port,
                value=":flag_" + server["country"] + ": " + server["name"],
            )
        )

    embed.fields = fields

    await ctx.send(embed=embed, ephemeral=True)


@check(check=interactions_validate_role)
@slash_command(
    name="monitor", description="Begin monitoring in this channel", dm_permission=False
)
async def monitor(ctx: SlashContext):
    server_choices = []

    for ip_port, server in config["servers"].items():
        server_choices.append(StringSelectOption(label=server["name"], value=ip_port))

    if len(server_choices) == 0:
        await ctx.send("No available servers - add one with /addserver", delete_after=5, ephemeral=True)

        return

    components = StringSelectMenu(
        *server_choices,
        placeholder="Select servers to monitor",
        min_values=1,
        max_values=len(server_choices)
    )

    msg = await ctx.send("Select a server to monitor", components=components)

    try:
        used_component = await bot.wait_for_component(
            components=components,
            check=component_validate_role,
            timeout=15
        )
    except TimeoutError:
        await msg.delete()
        pass
    else:
        servers_to_monitor = used_component.ctx.values
        channel_id = str(used_component.ctx.channel_id)
        message_id = str(used_component.ctx.message_id)
        channel_message_ids = channel_id + ":" + message_id
        config["active_messages"][channel_message_ids] = servers_to_monitor
        global_vars["cached_message_objects"][channel_message_ids] = used_component.ctx.message
        await used_component.ctx.edit_origin(
            content="\u200b",
            components=[],
            embed=await generate_embed(servers_to_monitor, 0)
        )
        write_config()


@Task.create(IntervalTrigger(seconds=60))
async def update_status_task():
    await update_status()


bot.start(token)
