import asyncio
from collections import deque


class DownloadQueue:
    def __init__(self, max_concurrent: int = 1):
        self.max_concurrent = max_concurrent

        self.queue = deque()
        self.workers = []

        self._active = 0
        self._condition = asyncio.Condition()

    async def add(self, job):
        """
        Add a job to the queue.

        Returns:
            0  -> job can start processing immediately
            >0 -> job's position among waiting jobs
        """

        async with self._condition:
            # If all workers are busy, this job has to wait.
            if self._active >= self.max_concurrent:
                position = len(self.queue) + 1
            else:
                # No worker is currently active.
                # This job can start immediately.
                position = 0

            self.queue.append(job)

            self._condition.notify()

            return position

    async def worker(self):
        while True:
            async with self._condition:

                while not self.queue:
                    await self._condition.wait()

                job = self.queue.popleft()

                self._active += 1

            try:
                await job()

            except Exception as e:
                print(
                    f"❌ Queue job error: "
                    f"{type(e).__name__}: {e}"
                )

            finally:
                async with self._condition:
                    self._active -= 1

    async def start(self):
        """
        Start the queue workers.
        """

        for _ in range(self.max_concurrent):
            worker = asyncio.create_task(
                self.worker()
            )

            self.workers.append(worker)
            
    async def stop(self):
        """
        Stop all queue workers cleanly.
        """
        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(
            *self.workers,
            return_exceptions=True
        )

        self.workers.clear()

    async def waiting(self):
        """
        Return the number of jobs waiting.
        """

        async with self._condition:
            return len(self.queue)

    async def active(self):
        """
        Return the number of jobs currently processing.
        """

        async with self._condition:
            return self._active

    def size(self):
        """
        Return the number of jobs waiting.

        Kept for compatibility with existing code.
        """

        return len(self.queue)