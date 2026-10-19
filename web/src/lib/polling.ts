export function startPolling(options: {
  poll: (signal: AbortSignal) => Promise<void>;
  interval: () => number;
  onError: (message: string) => void;
  timeoutMs?: number;
}): { stop: () => void; wake: () => void } {
  let stopped = false;
  let inFlight = false;
  let failures = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let controller: AbortController | undefined;
  async function tick() {
    if (stopped || inFlight) return;
    inFlight = true;
    controller = new AbortController();
    const deadline = setTimeout(() => controller?.abort(), options.timeoutMs ?? 10000);
    try {
      await options.poll(controller.signal);
      failures = 0;
      if (!stopped) options.onError('');
    } catch (cause) {
      if (!stopped) {
        failures += 1;
        options.onError(cause instanceof Error ? cause.message : 'Console connection failed.');
      }
    } finally {
      clearTimeout(deadline);
      inFlight = false;
      if (!stopped) timer = setTimeout(() => void tick(), Math.min(60000, options.interval() * 2 ** Math.min(failures, 4)));
    }
  }
  void tick();
  return {
    stop() { stopped = true; clearTimeout(timer); controller?.abort(); },
    wake() { clearTimeout(timer); if (!inFlight) void tick(); }
  };
}
