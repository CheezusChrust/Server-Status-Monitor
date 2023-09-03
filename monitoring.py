from interactions import Task, IntervalTrigger, Embed, EmbedField
from config import config, global_vars, write_config
import a2s
from asyncio import TimeoutError as ATimeoutError
from time import time as curtime


async def generate_embed(servers: list, query_time: float) -> Embed:
    fields = []

    for ip_port in servers:
        if ip_port not in config["servers"]:
            fields.append(EmbedField(
                name=f":grey_question: {ip_port}",
                value="Server not in config!",
                inline=False
            ))

            continue

        server_data = None

        if ip_port in global_vars["server_data"]:
            server_data = global_vars["server_data"][ip_port]

        flag_emoji = ":flag_" + config["servers"][ip_port]["country"] + ":"
        join_link = f"**IP:** {ip_port}"
        extra_info = ""
        for k, v in config["servers"][ip_port]["notes"].items():
            extra_info += f"\n**{k}:** {v}"

        if server_data is not None and server_data.server_name is not None:
            server_name = f"{flag_emoji} {server_data.server_name}"
            player_count = f"**Player count:** {server_data.player_count}/{server_data.max_players}"
            map_name = f"**Map:** {server_data.map_name}"

            fields.append(EmbedField(
                name=server_name,
                value=join_link + "\n"
                + player_count + "\n"
                + map_name
                + extra_info,
                inline=False
            ))
        else:
            fields.append(EmbedField(
                name=f"{flag_emoji} {config['servers'][ip_port]['name']} **[OFFLINE]**",
                value=join_link + "\n"
                + "**Player count:** N/A\n"
                + "**Map:** N/A"
                + extra_info,
                inline=False
            ))

    fields.append(EmbedField(
        name="\u200b",
        value=f"Last updated <t:{int(curtime())}:R>\nQuery took `{round(query_time, 2)} seconds`",
        inline=False,
    ))

    return Embed(title=":computer: Server Status", description="\u200b\n", fields=fields)


async def get_server_info(ip: str, port: int) -> a2s.SourceInfo:
    server_name = config["servers"][f"{ip}:{port}"]["name"]

    try:
        return await a2s.ainfo((ip, port), timeout=5)
    except (a2s.BrokenMessageError, a2s.BufferExhaustedError) as exception:
        print(f"a2s error on server {ip} [{server_name}]: {exception}")

        return a2s.SourceInfo()
    except (TimeoutError, ATimeoutError):
        print(f"a2s timeout on server {ip} [{server_name}]")

        return a2s.SourceInfo()


async def monitor_servers():
    server_data = global_vars["server_data"]

    query_start = curtime()
    for ip_port, server in config["servers"].items():
        ip, port = ip_port.split(":")
        port = int(port)
        info = await get_server_info(ip, port)

        if ip_port not in server_data:
            server_data[ip_port] = {}

        server_data[ip_port] = info
    query_time = curtime() - query_start

    marked_for_removal = []
    cached_message_objects = global_vars["cached_message_objects"]
    for channel_message_ids, servers in config["active_messages"].items():
        if channel_message_ids not in cached_message_objects:
            print(f"Message not yet cached: {channel_message_ids}")
            channel_id, message_id = channel_message_ids.split(":")
            channel = await global_vars["bot"].fetch_channel(channel_id)

            cached_message_objects[channel_message_ids] = await channel.fetch_message(message_id)

            print("Adding message " + message_id + " from channel " + channel_id)

        try:
            await cached_message_objects[channel_message_ids].edit(
                content="\u200b",
                embed=await generate_embed(servers, query_time)
            )
        except AttributeError:
            print(f"Message appears to be deleted, removing from config: {channel_message_ids}")
            marked_for_removal.append(channel_message_ids)
        except Exception as e:
            if "HTTPException" in str(e):
                print(f"Message appears to be deleted, removing from config: {channel_message_ids}")
                marked_for_removal.append(channel_message_ids)
            else:
                print(f"Unknown error: {e}")

    for channel_message_ids in marked_for_removal:
        del cached_message_objects[channel_message_ids]
        del config["active_messages"][channel_message_ids]

        write_config()


@Task.create(IntervalTrigger(seconds=30))
async def monitor_task():
    await monitor_servers()
