
async def list_commands(self, message, args):
    commands_list = []
        for key,value in self.command_dict.items():
            commands_list.append(self.command_prefix + " " + value["desc"])
            commands_string = "\n".join(commands_list)
    await message.channel.send("These are the commands:\n" + "```" + commands_string + "```")

async def debug(self, message, args):
    print("Thanks for waiting")
