import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import requests
import json
from dotenv import load_dotenv
import os

load_dotenv() 

intents = discord.Intents.default()
client = commands.Bot(command_prefix='cu!', intents=intents)

SCHEDULE_URL = """https://uisapppr3.njit.edu/scbldr/include/datasvc.php?p=/"""

listeners = {}
class CourseListener():
    def __init__(self, id: int, section_added: bool, section_removed: bool, any_section_opens: bool, any_honors_opens: bool, any_online_opens: bool):
        self.id = id
        self.section_added = section_added
        self.section_removed = section_removed
        self.any_section_opens = any_section_opens
        self.any_honors_opens = any_honors_opens
        self.any_online_opens = any_online_opens
    def __eq__(self, other) -> bool:
        return other.id == self.id
class SectionListener():
    def __init__(self, id: int, opened: bool, closed: bool, prof_update: bool, time_update: bool) -> None:
        self.id = id
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
                    obj['section_added'],
                    obj['section_removed'],
                    obj['any_section_opens'],
                    obj['any_honors_opens'],
                    obj['any_online_opens']
                )
            elif obj['type'] == 'SectionListener':
                return SectionListener(
                    obj['id'],
                    obj['opened'],
                    obj['closed'],
                    obj['prof_update'],
                    obj['time_update']
                )
        return obj

def get_json():
    raw_content = requests.get(SCHEDULE_URL).content[15:-53]
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
            reconstructed_section['seats'] = section[3].split('/')[1].strip()
            reconstructed_section['taken_seats'] = section[3].split('/')[0].strip()
            reconstructed_section['prof'] = section[4]
            reconstructed_section['honors'] = 'H' in section[1]
            reconstructed_section['online'] = section[1][0] == '4'
            reconstructed_section['comment'] = section[7]
            reconstructed_section['times'] = section[9]

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
            listener = CourseListener(interaction.user.id, section_added, section_removed, any_section_opens, any_honors_opens, any_online_opens)
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
            listener = SectionListener(interaction.user.id, opens, closes, prof_changes, timing_room_changes)

            if section not in listeners[course_code]['sections']:
                listeners[course_code]['sections'][section] = []

            listeners[course_code]['sections'][section][:] = [obj for obj in listeners[course_code]['sections'][section] if obj != listener]
            listeners[course_code]['sections'][section].append(listener)

        else:
            await interaction.response.send_message("Course code not found, please double-check and try again.")




# Function to check for changes and send a message if there is one
async def check_for_changes():
    previous_json_data = get_json()

    while True:
        await asyncio.sleep(10)  # Sleep for 60 seconds

        json_data = get_json()
        previous_json_data = json_data

        with open('listeners.json', 'w') as writer:
            json.dump(listeners, writer, cls=ListenEncoder)
        print("Backed up and ticked next update")
        
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    client.tree.add_command(FollowGroup(name='follow', description='Follow a course or section'))
    client.tree.copy_global_to(guild=client.get_guild(610972034738159617))
    await client.tree.sync()

    client.loop.create_task(check_for_changes())

client.run(os.getenv('BOT_TOKEN'))