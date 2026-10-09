"""Keep cancellable network work off the synchronous reader's event-loop exit.

asyncio.run waits for its DNS executor on shutdown even after an HTTP timeout.
An outstanding lookup can therefore delay the caller past the live deadline.
This research transport uses one background loop: the caller stops waiting and
cancels its coroutine, without joining a pending DNS lookup in the critical path.
It never retries, and a late result has no callback to an advisor/state store.
"""
import asyncio
from threading import Event, Thread


class NetworkLoop:
    def __init__(self):
        ready=Event()
        def run():
            self.loop=asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop);ready.set();self.loop.run_forever()
        self.thread=Thread(target=run,name='bounded-research-network',daemon=True)
        self.thread.start()
        if not ready.wait(2):raise RuntimeError('Research network loop did not start.')

    async def request(self,coroutine,timeout):
        future=asyncio.run_coroutine_threadsafe(coroutine,self.loop)
        try:
            async with asyncio.timeout(timeout):
                return await asyncio.wrap_future(future)
        finally:
            if not future.done():future.cancel()


NETWORK=NetworkLoop()
