import argparse
from git_info import get_branch_info
from renderer import render


def main():
    parser = argparse.ArgumentParser(description="Git branch structure visualizer")
    parser.add_argument("--path", default=".", help="Path to git repository")
    args = parser.parse_args()

    try:
        info = get_branch_info(args.path)
        print(render(info))
    except RuntimeError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
