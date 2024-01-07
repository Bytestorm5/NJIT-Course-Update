import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import requests
import json
from dotenv import load_dotenv
import os
import datetime
import time

load_dotenv() 

intents = discord.Intents.default()
client = commands.Bot(command_prefix='cu!', intents=intents)

SCHEDULE_URL = """https://uisapppr3.njit.edu/scbldr/include/datasvc.php?p=/"""

listeners= {}
class CourseListener():
    def __init__(self, id: int, is_user: bool, section_added: bool, section_removed: bool, any_section_opens: bool, any_honors_opens: bool, any_online_opens: bool):
        self.id = id
        self.is_user = is_user
        self.section_added = section_added
        self.section_removed = section_removed
        self.any_section_opens = any_section_opens
        self.any_honors_opens = any_honors_opens
        self.any_online_opens = any_online_opens
    def __eq__(self, other) -> bool:
        return other.id == self.id
class SectionListener():
    def __init__(self, id: int, is_user: bool, opened: bool, closed: bool, prof_update: bool, time_update: bool) -> None:
        self.id = id
        self.is_user = is_user
        self.opened = opened
        self.closed = closed
        self.prof_update = prof_update
        self.time_update = time_update
    def __eq__(self, other) -> bool:
        return other.id == self.id


class ListenEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, CourseListener):
            return {
                'type': 'CourseListener',
                'id': obj.id,
                'is_user': obj.is_user,
                'section_added': obj.section_added,
                'section_removed': obj.section_removed,
                'any_section_opens': obj.any_section_opens,
                'any_honors_opens': obj.any_honors_opens,
                'any_online_opens': obj.any_online_opens
            }
        elif isinstance(obj, SectionListener):
            return {
                'type': 'SectionListener',
                'id': obj.id,
                'is_user': obj.is_user,
                'opened': obj.opened,
                'closed': obj.closed,
                'prof_update': obj.prof_update,
                'time_update': obj.time_update
            }
        return super().default(obj)
class ListenDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        if 'type' in obj:
            if obj['type'] == 'CourseListener':
                return CourseListener(
                    obj['id'],
                    obj['is_user'],
                    obj['section_added'],
                    obj['section_removed'],
                    obj['any_section_opens'],
                    obj['any_honors_opens'],
                    obj['any_online_opens']
                )
            elif obj['type'] == 'SectionListener':
                return SectionListener(
                    obj['id'],
                    obj['is_user'],
                    obj['opened'],
                    obj['closed'],
                    obj['prof_update'],
                    obj['time_update']
                )
        return obj

def get_json():
    raw_content = requests.get(SCHEDULE_URL).content[15:-55]
    raw_json = json.loads(raw_content)

    # They called me a madman
    # They mightve been right
    reconstructed_dict = {}
    for course in raw_json:
        reconstructed_course = {}
        reconstructed_course['sections'] = {}

        reconstructed_course['name'] = course[0]
        reconstructed_course['full_name'] = course[1]
        reconstructed_course['credits'] = course[2]

        for section in course[3:]:
            reconstructed_course['name'] = section[0]
            reconstructed_course['full_name'] = section[8]

            reconstructed_section = {}

            reconstructed_section['name'] = section[1]
            reconstructed_section['call'] = section[2]
            reconstructed_section['seats'] = int(section[3].split('/')[1].strip())
            reconstructed_section['taken_seats'] = int(section[3].split('/')[0].strip())
            reconstructed_section['prof'] = section[4]
            reconstructed_section['honors'] = 'H' in section[1] or 'honors' in str(section[7]).lower()
            reconstructed_section['online'] = section[1][0] == '4' or 'online' in str(section[7]).lower()
            reconstructed_section['comment'] = section[7]
            reconstructed_section['times'] = set([tuple(time) for time in section[9]])

            reconstructed_course['sections'][section[1]] = reconstructed_section
        
        reconstructed_dict[reconstructed_course['name']] = reconstructed_course
    
    return reconstructed_dict

previous_json_data = get_json()

with open('listeners.json','r') as reader:
    listeners = json.load(reader, cls=ListenDecoder)
    reader.close()

class FollowGroup(app_commands.Group):
    @app_commands.command()
    async def course(self, interaction: discord.Interaction, course_code: str, section_added: bool, section_removed: bool, any_section_opens: bool, any_honors_opens: bool, any_online_opens: bool):
        if course_code in previous_json_data or course_code in listeners:            
            # Add course listener
            listener = CourseListener(interaction.user.id, True, section_added, section_removed, any_section_opens, any_honors_opens, any_online_opens)
            if course_code in listeners:
                # Remove all other listeners with this id
                listeners[course_code]['listeners'][:] = [obj for obj in listeners[course_code]['listeners'] if obj != listener]

                listeners[course_code]['listeners'].append(listener)
            else:
                listeners[course_code] = {}
                listeners[course_code]['listeners'] = [listener]

            message = f"You will be DMed when any of the following occur to {course_code}:\n"
            if section_added:
                message += "- A section is added to this course\n"
            if section_removed:
                message += "- A section is removed from this course\n"
            if any_section_opens:
                message += "- Any section gets free seats\n"
            if any_honors_opens:
                message += "- Any Honors section gets free seats\n"
            if any_online_opens:
                message += "- Any Online section gets free seats\n"

            await interaction.response.send_message(message)
        else:
            await interaction.response.send_message("Course code not found, please double-check and try again.")
    
    @app_commands.command()
    async def section(self, interaction: discord.Interaction, course_code: str, section: str, opens: bool, closes: bool, prof_changes: bool, timing_room_changes: bool):
        if course_code in previous_json_data and section in previous_json_data[course_code].get('sections', {}):
            listener = SectionListener(interaction.user.id, True, opens, closes, prof_changes, timing_room_changes)

            if section not in listeners[course_code]['sections']:
                listeners[course_code]['sections'][section] = []

            listeners[course_code]['sections'][section][:] = [obj for obj in listeners[course_code]['sections'][section] if obj != listener]
            listeners[course_code]['sections'][section].append(listener)

        else:
            await interaction.response.send_message("Course code not found, please double-check and try again.")

    # DEBUG ONLY

    # @app_commands.command()
    # async def sim_add(self, interaction: discord.Interaction, course_code: str, section: str):
    #     if course_code in previous_json_data:
    #         if section in previous_json_data[course_code]['sections']:
    #             del previous_json_data[course_code]['sections'][section]
    #             await interaction.response.send_message("Success")
    #             return
    #     await interaction.response.send_message("Must already exist to simulate add")

    # @app_commands.command()
    # async def sim_open(self, interaction: discord.Interaction, course_code: str, section: str):
    #     if course_code in previous_json_data:
    #         if section in previous_json_data[course_code]['sections']:
    #             section_dict = previous_json_data[course_code]['sections'][section]
    #             section_dict['taken_seats'] = section_dict['seats']
    #             previous_json_data[course_code]['sections'][section] = section_dict

    #             await interaction.response.send_message("Success")
    #             return
    #     await interaction.response.send_message("Must already exist to simulate open")
class FeedGroup(app_commands.Group):
    @app_commands.command()
    async def course(self, interaction: discord.Interaction, course_code: str, section_added: bool, section_removed: bool, any_section_opens: bool, any_honors_opens: bool, any_online_opens: bool):
        if course_code in previous_json_data or course_code in listeners:            
            # Add course listener
            if interaction.channel_id == None:
                await interaction.response.send_message("Feed commands can only be executed in a channel")
                return
            listener = CourseListener(interaction.channel_id, False, section_added, section_removed, any_section_opens, any_honors_opens, any_online_opens)
            if course_code in listeners:
                # Remove all other listeners with this id
                listeners[course_code]['listeners'][:] = [obj for obj in listeners[course_code]['listeners'] if obj != listener]

                listeners[course_code]['listeners'].append(listener)
            else:
                listeners[course_code] = {}
                listeners[course_code]['listeners'] = [listener]

            message = f"A message will be sent in this channel when any of the following occur to {course_code}:\n"
            if section_added:
                message += "- A section is added to this course\n"
            if section_removed:
                message += "- A section is removed from this course\n"
            if any_section_opens:
                message += "- Any section gets free seats\n"
            if any_honors_opens:
                message += "- Any Honors section gets free seats\n"
            if any_online_opens:
                message += "- Any Online section gets free seats\n"

            await interaction.response.send_message(message)
        else:
            await interaction.response.send_message("Course code not found, please double-check and try again.")
    
    @app_commands.command()
    async def section(self, interaction: discord.Interaction, course_code: str, section: str, opens: bool, closes: bool, prof_changes: bool, timing_room_changes: bool):
        if course_code in previous_json_data and section in previous_json_data[course_code].get('sections', {}):
            if interaction.channel_id == None:
                await interaction.response.send_message("Feed commands can only be executed in a channel")
                return
            listener = SectionListener(interaction.channel_id, False, opens, closes, prof_changes, timing_room_changes)

            if 'sections' not in listeners[course_code]:
                listeners[course_code]['sections'] = {}
            if section not in listeners[course_code]['sections']:
                listeners[course_code]['sections'][section] = []

            listeners[course_code]['sections'][section][:] = [obj for obj in listeners[course_code]['sections'][section] if obj != listener]
            listeners[course_code]['sections'][section].append(listener)

        else:
            await interaction.response.send_message("Course code not found, please double-check and try again.")

    @app_commands.command()
    async def all(self, interaction: discord.Interaction):
        if interaction.channel_id == None:
            await interaction.response.send_message("Feed commands can only be executed in a channel")
            return
        if 'all' not in listeners:
            listeners['all'] = [interaction.channel_id]
        else:
            listeners['all'].append(interaction.channel_id)
        await interaction.response.send_message("This channel will now receive __all__ updates to the course schedule. Do `/unfeed all` to undo.")
        
class UnfollowGroup(app_commands.Group):
    @app_commands.command()
    async def course(self, interaction: discord.Interaction, course_code: str):
        if course_code in listeners:
            listeners[course_code]['listeners'][:] = [obj for obj in listeners[course_code]['listeners'] if obj.id != interaction.user.id]
        await interaction.response.send_message(f"Sucessfully unfollowed course {course_code}")
    
    @app_commands.command()
    async def section(self, interaction: discord.Interaction, course_code: str, section: str):
        if course_code in previous_json_data and section in previous_json_data[course_code].get('sections', {}):
            if section not in listeners[course_code]['sections']:
                listeners[course_code]['sections'][section] = []

            listeners[course_code]['sections'][section][:] = [obj for obj in listeners[course_code]['sections'][section] if obj.id != interaction.user.id]
        await interaction.response.send_message(f"Sucessfully unfollowed section {section} of {course_code}")  

class UnfeedGroup(app_commands.Group):
    @app_commands.command()
    async def course(self, interaction: discord.Interaction, course_code: str):
        if interaction.channel_id == None:
            await interaction.response.send_message("Unfeed commands can only be executed in a channel")
            return
        if course_code in listeners:
            listeners[course_code]['listeners'][:] = [obj for obj in listeners[course_code]['listeners'] if obj.id != interaction.channel_id]
        await interaction.response.send_message(f"Sucessfully unfed course {course_code}")
    
    @app_commands.command()
    async def section(self, interaction: discord.Interaction, course_code: str, section: str):
        if interaction.channel_id == None:
            await interaction.response.send_message("Unfeed commands can only be executed in a channel")
            return
        if course_code in previous_json_data and section in previous_json_data[course_code].get('sections', {}):
            if section not in listeners[course_code]['sections']:
                listeners[course_code]['sections'][section] = []

            listeners[course_code]['sections'][section][:] = [obj for obj in listeners[course_code]['sections'][section] if obj.id != interaction.channel_id]
        await interaction.response.send_message(f"Sucessfully unfed section {section} of {course_code}")

    @app_commands.command()
    async def all(self, interaction: discord.Interaction):
        if interaction.channel_id == None:
            await interaction.response.send_message("Unfeed commands can only be executed in a channel")
            return
        listeners['all'][:] = [obj for obj in listeners['all'] if obj.id != interaction.channel_id]

class Notifier():
    def __init__(self) -> None:
        pass
    
    async def send_to_listener(self, listener: CourseListener | SectionListener, embed: discord.Embed):
        if listener.is_user:
            user = client.get_user(listener.id)
            if user == None:
                return
            await user.send(embed=embed)
        else:
            channel = client.get_channel(listener.id)                    
            # Private or GC channels should always come in as a DMChannel or GroupChannel
            # So send() will always be defined
            if channel == None or channel.type != discord.ChannelType.text: # type: ignore
                return
            await channel.send(embed=embed) # type: ignore
    async def send_to_alls(self, embed):
        global listeners
        print(f"[DEBUG]: \"All\" Listeners: {listeners.get('all', [])}")
        print(f" - Found 'all' Field: {'all' in listeners}")
        
        for listener in listeners.get('all', []):
            channel = client.get_channel(listener)                    
            if channel == None or channel.type != discord.ChannelType.text: # type: ignore
                return
            await channel.send(embed=embed) # type: ignore
    
    async def section_add(self, course_code, section):
        course_listens: list[CourseListener] = listeners.get(course_code, {}).get('listeners', [])
        # section_listens = course_listens['sections'][section]
        
        embed = discord.Embed(
            color=discord.Color(0x23A55A),
            title=f"{course_code} section added!",
            description=f"The section {course_code}-{section} has just been added."
        )        
        embed.set_footer(text="NJIT Course Update is an unofficial tool. Refer to the Self-Service Banner or an advisor for the most up-to-date information.")
        
        for listener in course_listens:
            if listener.section_added:
                await self.send_to_listener(listener, embed)
        await self.send_to_alls(embed)
                    
    async def section_remove(self, course_code, section):
        course_listens: list[CourseListener] = listeners.get(course_code, {}).get('listeners', [])
        # section_listens = course_listens['sections'][section]
        
        embed = discord.Embed(
            color=discord.Color(0xA32323),
            title=f"{course_code} section removed!",
            description=f"The section {course_code}-{section} has just been removed."
        )        
        embed.set_footer(text="NJIT Course Update is an unofficial tool. Refer to the Self-Service Banner or an advisor for the most up-to-date information.")
        
        for listener in course_listens:
            if listener.section_removed:
                await self.send_to_listener(listener, embed)
        await self.send_to_alls(embed)
        
    async def section_open(self, course_code, section):
        course_listens: list[CourseListener] = listeners.get(course_code, {}).get('listeners', [])
        section_listens: list[SectionListener] = listeners.get(course_code, {}).get('sections', {}).get(section, [])
        section_data = previous_json_data[course_code]['sections'][section]
        
        embed = discord.Embed(
            color=discord.Color(0x23A55A),
            title=f"{course_code}-{section} has open seats!",
            description=f"There are at least two seats open in {course_code}-{section}, meaning that you should be able to join with no waitlist."
        )        
        embed.set_footer(text="NJIT Course Update is an unofficial tool. Refer to the Self-Service Banner or an advisor for the most up-to-date information.")
               
        notifed = []
        
        for listener in course_listens:
            # The miniscule impact to efficiency is worth the readability
            # Probably
            send_notif = listener.any_section_opens
            send_notif = send_notif or (section_data['honors'] and listener.any_honors_opens)
            send_notif = send_notif or (section_data['online'] and listener.any_online_opens)
            
            if send_notif:
                notifed.append(listener.id)
                await self.send_to_listener(listener, embed)
                    
        for listener in section_listens:
            if listener.opened and listener.id not in notifed:
                await self.send_to_listener(listener, embed)
        await self.send_to_alls(embed)
                
    async def section_close(self, course_code, section):
        course_listens: list[CourseListener] = listeners.get(course_code, {}).get('listeners', [])
        section_listens: list[SectionListener] = listeners.get(course_code, {}).get('sections', {}).get(section, [])
        section_data = previous_json_data[course_code]['sections'][section]
        
        embed = discord.Embed(
            color=discord.Color(0xA32323),
            title=f"{course_code}-{section} has no open seats!",
            description=f"There are no longer any open seats in {course_code}-{section}"
        )        
        embed.set_footer(text="NJIT Course Update is an unofficial tool. Refer to the Self-Service Banner or an advisor for the most up-to-date information.")
               
        notifed = []
        
        for listener in course_listens:
            # The miniscule impact to efficiency is worth the readability
            # Probably
            send_notif = listener.any_section_opens
            send_notif = send_notif or (section_data['honors'] and listener.any_honors_opens)
            send_notif = send_notif or (section_data['online'] and listener.any_online_opens)
            
            if send_notif:
                notifed.append(listener.id)
                await self.send_to_listener(listener, embed)
                    
        for listener in section_listens:
            if listener.opened and listener.id not in notifed:
                await self.send_to_listener(listener, embed)
        await self.send_to_alls(embed)
                
    async def section_prof_change(self, course_code, section, profs: tuple):
        section_listens: list[SectionListener] = listeners.get(course_code, {}).get('sections', {}).get(section, [])
        
        print(f"PROFS: {profs}")
        
        #if profs != None:
        if profs[0] == None or len(profs[0]) == 0:
            profs[0] = "Unknown"
        if profs[1] == None or len(profs[1]) == 0:
            profs[1] = "Unknown"
        embed = discord.Embed(
            color=discord.Color(0xFFFFFF),
            title=f"{course_code}-{section} has changed professors!",
            description=f"The professor for {course_code}-{section} has changed from {str(profs[0])} to {str(profs[1])}."
        )  
        # else:
        #     embed = discord.Embed(
        #         color=discord.Color(0xFFFFFF),
        #         title=f"{course_code}-{section} has changed professors!",
        #         description=f"The professor for {course_code}-{section} has changed. Check your course schedule for details."
        #     )        
        embed.set_footer(text="NJIT Course Update is an unofficial tool. Refer to the Self-Service Banner or an advisor for the most up-to-date information.")
        
        for listener in section_listens:
            if listener.prof_update:
                await self.send_to_listener(listener, embed)
        await self.send_to_alls(embed)
                
    async def section_time_change(self, course_code, section):
        section_listens: list[SectionListener] = listeners.get(course_code, {}).get('sections', {}).get(section, [])
        
        embed = discord.Embed(
            color=discord.Color(0xFFD800),
            title=f"{course_code}-{section} has changed times!",
            description=f"The timings or room for {course_code}-{section} has changed. Check your course schedule for details and make sure there are no conflicts."
        )        
        embed.set_footer(text="NJIT Course Update is an unofficial tool. Refer to the Self-Service Banner or an advisor for the most up-to-date information.")
        
        for listener in section_listens:
            if listener.time_update:
                await self.send_to_listener(listener, embed)
        await self.send_to_alls(embed)

NOTIFICATION_MANAGER = Notifier()

def print_with_timestamp(message):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

async def check_for_changes():
    global previous_json_data
    previous_json_data = get_json()

    while True:
        await asyncio.sleep(60 * 5) 

        update_start = time.perf_counter()
        change_count = 0

        json_data = get_json()

        for course in set(json_data.keys()).union(set(previous_json_data.keys())):
            prev_state = previous_json_data.get(course, {'name':course, 'sections': {}})
            current_state = json_data.get(course, {'name':course, 'sections': {}})

            for section in current_state['sections'].keys():
                if section not in prev_state['sections']:
                    change_count += 1
                    await NOTIFICATION_MANAGER.section_add(course, section)
                    
            for section in prev_state['sections'].keys():
                if section not in current_state['sections']:
                    change_count += 1
                    await NOTIFICATION_MANAGER.section_remove(course, section)
            
            for section in current_state['sections']:
                if section not in current_state['sections'] or section not in prev_state['sections']:
                    continue
                prev_section = prev_state['sections'][section]
                curr_section = current_state['sections'][section]
                
                # Was Open
                if prev_section['taken_seats']+1 < prev_section['seats']:
                    # Now closed
                    if curr_section['taken_seats'] >= prev_section['seats']:
                        print_with_timestamp(f"")
                        change_count += 1
                        await NOTIFICATION_MANAGER.section_close(course, curr_section['name'])
                        
                # Was Closed
                if prev_section['taken_seats']+1 >= prev_section['seats']:
                    # Now Open
                    if curr_section['taken_seats']+1 < prev_section['seats']:
                        change_count += 1
                        await NOTIFICATION_MANAGER.section_open(course, curr_section['name'])
                        
                if prev_section['prof'] != curr_section['prof']:                    
                    change_count += 1
                    await NOTIFICATION_MANAGER.section_prof_change(course, curr_section['name'], profs=(prev_section['prof'], curr_section['prof']))
                    
                if prev_section['times'] != curr_section['times']:
                    change_count += 1
                    await NOTIFICATION_MANAGER.section_time_change(course, curr_section['name'])

        with open('listeners.json', 'w') as writer:
            json.dump(listeners, writer, cls=ListenEncoder)

        previous_json_data = json_data


        print_with_timestamp(f"Ticked update & listeners in {time.perf_counter() - update_start} seconds")
        print_with_timestamp(f"Pushed notifs for {change_count} schedule changes")
        print()
        
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    client.tree.add_command(FollowGroup(name='follow', description='Follow a course or section'))
    client.tree.add_command(FeedGroup(name='feed', description='Feed updates to a course or section into the current channel'))
    client.tree.add_command(UnfollowGroup(name='unfollow', description='Unfollow a course or section'))
    client.tree.add_command(UnfeedGroup(name='unfeed', description='Stop feeding updates to a course or section to the current channel'))
    
    debug_server = client.get_guild(610972034738159617)
    if debug_server != None:
        client.tree.copy_global_to(guild=debug_server)
    
    await client.tree.sync()

    client.loop.create_task(check_for_changes())

client.run(os.getenv('BOT_TOKEN'))