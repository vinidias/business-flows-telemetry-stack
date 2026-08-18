"""
==============================================================================
Business Flows Telemetry Stack - End-to-End Pipeline Orchestrator
==============================================================================
Executes the full telemetry pipeline workflow:
  1. Data Extraction (MySQL/Postgres -> Parquet -> DuckDB)
  2. Data Modeling & Transformation (dbt run)
  3. Data Quality Testing (dbt test)
  4. Telemetry Metrics Push (DuckDB marts -> Grafana Cloud Prometheus)

Usage:
    python pipeline.py
==============================================================================
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("PipelineOrchestrator")


def run_command(command: list, cwd: Path, step_name: str) -> bool:
    """
    Execute a shell command with real-time output streaming.

    Args:
        command: List of command arguments.
        cwd: Working directory.
        step_name: Descriptive name of the step.

    Returns:
        bool: True if command exited with code 0, False otherwise.
    """
    logger.info(">>> Starting Step: %s", step_name)
    logger.info("Running command: %s (cwd: %s)", " ".join(command), cwd)
    start_time = time.time()

    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        # Stream stdout/stderr in real-time
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                line_str = line.rstrip()
                if line_str:
                    logger.info("[%s] %s", step_name, line_str)
            process.stdout.close()

        return_code = process.wait()
        elapsed = time.time() - start_time

        if return_code == 0:
            logger.info("<<< Step '%s' completed successfully in %.2fs", step_name, elapsed)
            return True
        else:
            logger.error("<<< Step '%s' FAILED with exit code %d (took %.2fs)", step_name, return_code, elapsed)
            return False

    except Exception as e:
        logger.error("Exception during step '%s': %s", step_name, str(e))
        return False


def main() -> None:
    """Run full end-to-end telemetry pipeline."""
    pipeline_dir = Path(__file__).resolve().parent
    analytics_dir = pipeline_dir / "analytics"
    python_exe = sys.executable

    logger.info("=================================================================")
    logger.info("   BUSINESS FLOWS TELEMETRY STACK - PIPELINE EXECUTION START    ")
    logger.info("=================================================================")
    overall_start_time = time.time()

    steps = [
        {
            "name": "1. Extract Data",
            "cmd": [python_exe, str(pipeline_dir / "extract.py")],
            "cwd": pipeline_dir,
        },
        {
            "name": "2. dbt Transform (dbt run)",
            "cmd": ["dbt", "run", "--profiles-dir", "."],
            "cwd": analytics_dir,
        },
        {
            "name": "3. dbt Data Quality Tests (dbt test)",
            "cmd": ["dbt", "test", "--profiles-dir", "."],
            "cwd": analytics_dir,
        },
        {
            "name": "4. Push Telemetry Metrics to Grafana Cloud",
            "cmd": [python_exe, str(pipeline_dir / "push_metrics.py")],
            "cwd": pipeline_dir,
        },
    ]

    execution_summary = []
    has_failure = False

    for step in steps:
        step_name = step["name"]
        step_start = time.time()
        success = run_command(step["cmd"], step["cwd"], step_name)
        step_duration = time.time() - step_start

        execution_summary.append({
            "step": step_name,
            "status": "SUCCESS" if success else "FAILED",
            "duration": f"{step_duration:.2f}s",
        })

        if not success:
            has_failure = True
            logger.error("Pipeline execution halted due to failure in step: %s", step_name)
            break

    overall_duration = time.time() - overall_start_time
    logger.info("=================================================================")
    logger.info("                    PIPELINE EXECUTION SUMMARY                   ")
    logger.info("=================================================================")
    for item in execution_summary:
        logger.info("  * %-45s [%s] (%s)", item["step"], item["status"], item["duration"])
    logger.info("Total Pipeline Duration: %.2fs", overall_duration)
    logger.info("=================================================================")

    if has_failure:
        sys.exit(1)
    else:
        logger.info("Pipeline completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
