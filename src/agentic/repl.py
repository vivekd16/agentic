import typer

def main():
    typer.echo("Welcome to the REPL!")
    while True:
        try:
            command = typer.prompt(">>> ")
            # Process the command here
            if command.lower() == "exit":
                break
            typer.echo(f"You entered: {command}")
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    typer.run(main)
    
def repl_loop(self):
        runner = ActorAgentRunner(self.agent)

        print(self.agent.welcome)
        print("press <enter> to quit")
        while True:
            prompt = input("> ").strip()
            if prompt == "quit" or prompt == "":
                break
            runner.start(prompt)

            for event in runner.next():
                # print("[event] " ,event.__dict__)
                if event is None:
                    break
                elif event.requests_input():
                    response = input(f"\n{event.request_message}\n>> ")
                    runner.continue_with(response)
                else:
                    if event.depth == 0:
                        print(event, end="")
            print()
