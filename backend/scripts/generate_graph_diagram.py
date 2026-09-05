import subprocess
from pathlib import Path

from app.orchestrator.graph import build_uncheckpointed_graph




def main():
    # ---------------------------------------------------------
    # Generate Mermaid content from the actual LangGraph
    # ---------------------------------------------------------
    support_graph = build_uncheckpointed_graph()
    mermaid = support_graph.get_graph().draw_mermaid()

    # ---------------------------------------------------------
    # Project root
    # ---------------------------------------------------------

    project_root = (
        Path(__file__).resolve().parent.parent.parent
    )

    # ---------------------------------------------------------
    # Output files
    # ---------------------------------------------------------

    mmd_file = project_root / "docs" / "support_workflow.mmd"
    png_file = project_root / "docs" / "support_workflow.png"

    # Make sure docs directory exists
    mmd_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Save Mermaid file
    # ---------------------------------------------------------

    mmd_file.write_text(
        mermaid,
        encoding="utf-8",
    )

    print(
        f"Mermaid file generated: {mmd_file}"
    )

    # ---------------------------------------------------------
    # Generate PNG image
    # ---------------------------------------------------------

    try:
        subprocess.run(
            [
                "npx",
                "-p",
                "@mermaid-js/mermaid-cli",
                "mmdc",
                "-i",
                str(mmd_file),
                "-o",
                str(png_file),
            ],
            check=True,
        )

        print(
            f"PNG image generated: {png_file}"
        )

    except subprocess.CalledProcessError as exc:
        print(
            "Could not generate PNG image."
        )
        print(exc)

    except FileNotFoundError:
        print(
            "Could not generate PNG image because "
            "'npx' was not found."
        )

    print(
        "\nWorkflow diagram generation completed."
    )


if __name__ == "__main__":
    main()