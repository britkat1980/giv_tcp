import asyncio
import types
import time

# A tiny harness that simulates the producer and consumer futures interactions
# without opening real sockets. It creates fake tx_queue and expected_responses
# and races frame_sent/result setting and cancellation to stress the code paths.

class DummyClient:
    def __init__(self):
        self.tx_queue = asyncio.Queue()
        self.expected_responses = {}

    async def _producer(self, tx_message_wait=0.01):
        while True:
            try:
                raw, fut = await self.tx_queue.get()
            except asyncio.CancelledError:
                break
            # Simulate write delay
            await asyncio.sleep(tx_message_wait)
            # Safely set frame future if active
            if fut and not fut.done() and not fut.cancelled():
                fut.set_result(True)
            self.tx_queue.task_done()

    async def _simulate_response(self, shape_hash, delay=0.02):
        # After delay, set the expected response future if still open
        await asyncio.sleep(delay)
        fut = self.expected_responses.get(shape_hash)
        if fut and not fut.done() and not fut.cancelled():
            fut.set_result('OK')

    async def send_request_and_await_response(self, raw_frame, shape_hash, timeout=0.1):
        loop = asyncio.get_running_loop()
        response_future = loop.create_future()
        # Cancel any existing
        existing = self.expected_responses.get(shape_hash)
        if existing and not existing.done():
            existing.cancel()
        self.expected_responses[shape_hash] = response_future

        frame_sent = loop.create_future()
        await self.tx_queue.put((raw_frame, frame_sent))

        # Wait for frame sent
        await asyncio.wait_for(frame_sent, timeout=timeout)

        # Wait for response or timeout
        try:
            res = await asyncio.wait_for(response_future, timeout=timeout)
            return res
        finally:
            # cleanup
            if self.expected_responses.get(shape_hash) is response_future:
                del self.expected_responses[shape_hash]

async def stress_test():
    c = DummyClient()
    prod = asyncio.create_task(c._producer())

    async def sender(i):
        try:
            shape = 'sh' + str(i % 3)
            # kick off a simulate_response that may race with cancel
            asyncio.create_task(c._simulate_response(shape, delay=0.01 * (i % 5)))
            res = await c.send_request_and_await_response(b'frame', shape, timeout=0.05)
            print('sender', i, 'got', res)
        except asyncio.TimeoutError:
            print('sender', i, 'timeout')
        except asyncio.CancelledError:
            print('sender', i, 'cancelled')
        except Exception as e:
            print('sender', i, 'error', type(e), e)

    tasks = [asyncio.create_task(sender(i)) for i in range(40)]
    await asyncio.gather(*tasks)
    prod.cancel()
    await asyncio.sleep(0.05)

if __name__ == '__main__':
    asyncio.run(stress_test())
