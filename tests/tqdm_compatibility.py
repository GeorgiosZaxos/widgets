"""
Complete tqdm Demonstration Suite

This module provides a comprehensive set of examples for utilizing the tqdm
progress bar library in various contexts, ranging from simple loops to
multithreaded execution and Pandas data manipulation.

Dependencies:
    pip install tqdm pandas numpy
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from widgets.progress.tqdm import tqdm, trange

# Configure basic logging to demonstrate compatibility with tqdm
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class TqdmDemonstrator:
    """A collection of methods demonstrating different tqdm functionalities."""

    @staticmethod
    def basic_iterable(items: list[str]) -> None:
        """Demonstrates wrapping a standard iterable."""
        logging.info("Starting basic iterable demonstration.")
        # 'unit' changes the suffix (e.g., it/s -> item/s)
        for _item in tqdm(items, desc="Processing Items", unit="item"):
            time.sleep(0.3)  # Simulate I/O or computation

    @staticmethod
    def trange_shortcut(iterations: int) -> None:
        """Demonstrates the trange shortcut for standard ranges."""
        logging.info("Starting trange shortcut demonstration.")
        # trange(N) is functionally identical to tqdm(range(N))
        for _ in trange(iterations, desc="Quick Range Loop"):
            time.sleep(0.05)

    @staticmethod
    def manual_update(total_size: int, chunk_size: int) -> None:
        """Demonstrates manual progress updates, typical for file downloads/streams."""
        logging.info("Starting manual update demonstration.")
        # Using a context manager ensures the progress bar terminates cleanly
        with tqdm(total=total_size, desc="Downloading Data", unit="B", unit_scale=True) as pbar:
            current = 0
            while current < total_size:
                step = min(chunk_size, total_size - current)
                time.sleep(0.1)  # Simulate network chunk retrieval
                pbar.update(step)
                current += step

    @staticmethod
    def nested_loops(outer_iterations: int, inner_iterations: int) -> None:
        """Demonstrates tracking multiple nested loops simultaneously."""
        logging.info("Starting nested loops demonstration.")
        for i in trange(outer_iterations, desc="Outer Loop", position=0):
            # leave=False clears the inner bar once it completes its cycle
            for _j in trange(
                inner_iterations, desc=f"Inner Loop (Outer {i})", position=1, leave=False
            ):
                time.sleep(0.1)

    @staticmethod
    def pandas_integration(rows: int = 50000) -> pd.DataFrame:
        """Demonstrates hooking tqdm into Pandas for DataFrame operations."""
        logging.info("Starting Pandas integration demonstration.")
        tqdm.pandas(desc="Applying Function to DataFrame")

        df = pd.DataFrame(np.random.randint(0, 100, (rows, 4)), columns=list("ABCD"))

        # Use progress_apply instead of standard apply
        df["A_squared"] = df["A"].progress_apply(lambda x: x**2 + time.sleep(0.00001) or x**2)
        return df

    @staticmethod
    def _worker_task(task_id: int) -> str:
        """Helper method simulating a threaded task."""
        time.sleep(np.random.uniform(0.1, 1.5))
        return f"Task {task_id} completed"

    @classmethod
    def concurrent_futures(cls, num_tasks: int = 20, max_workers: int = 5) -> list[str]:
        """Demonstrates wrapping concurrent.futures for multithreaded progress."""
        logging.info("Starting concurrent execution demonstration.")
        results: list[str] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks to the executor
            futures = {executor.submit(cls._worker_task, i): i for i in range(num_tasks)}

            # Wrap as_completed with tqdm to track finished threads
            for future in tqdm(
                as_completed(futures), total=num_tasks, desc="Thread Pool Execution"
            ):
                results.append(future.result())

        return results


def main() -> None:
    """Execute all tqdm demonstrations sequentially."""
    print("=== TQDM Comprehensive Demonstration ===\n")

    demo = TqdmDemonstrator()

    print("\n--- 1. Basic Iterable ---")
    demo.basic_iterable(["Alpha", "Beta", "Gamma", "Delta", "Epsilon"])

    print("\n--- 2. trange Shortcut ---")
    demo.trange_shortcut(50)

    print("\n--- 3. Manual Updates ---")
    demo.manual_update(total_size=1024 * 1024, chunk_size=1024 * 128)

    print("\n--- 4. Nested Loops ---")
    demo.nested_loops(outer_iterations=3, inner_iterations=10)

    print("\n--- 5. Pandas Integration ---")
    demo.pandas_integration()

    print("\n--- 6. Concurrent Futures ---")
    demo.concurrent_futures()

    print("\n=== All Demonstrations Complete ===")


if __name__ == "__main__":
    main()
