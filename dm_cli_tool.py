from src.adapters.cli.dm_cli import app


def main():
	import sys

	# Delegate to Typer app
	app(prog_name="dm", args=sys.argv[1:])


if __name__ == "__main__":
	main()
