"""CLI: python -m levi.analog <command> [options]

The analog bench counter: run the damped-spring demo, see what the
machine is made of, draw a nomograph, stack Fourier bars.
"""

from __future__ import annotations

import argparse

from . import bench, fourier, nomo


def _cmd_run(a) -> int:
    net = bench.damped_spring(m=a.m, c=a.c, k=a.k, x0=a.x0, v0=a.v0)
    trace, receipt = bench.simulate(net, t_end=a.t_end, dt=a.dt)
    print(
        "receipt: steps=%d dt=%g t_end=%g peak|dy/dt|=%.4g "
        "blocks_evaluated=%d ok=%s"
        % (
            receipt.steps_used,
            receipt.dt,
            receipt.t_end,
            receipt.peak_dy_dt,
            receipt.blocks_evaluated,
            receipt.ok,
        )
    )
    pos = trace.signals["pos"]
    vel = trace.signals["vel"]
    print("t=%.3f  x=%.6f  v=%.6f" % (trace.t[0], pos[0], vel[0]))
    print("t=%.3f  x=%.6f  v=%.6f" % (trace.t[-1], pos[-1], vel[-1]))
    print("x(t):")
    print(fourier.plot_ascii(pos, height=11))
    return 0


def _cmd_parts(a) -> int:
    net = bench.damped_spring(m=a.m, c=a.c, k=a.k, x0=a.x0, v0=a.v0)
    print("meccano view — what the demo would have been in brass:")
    for line in bench.parts_list(net):
        print("  " + line)
    return 0


def _cmd_nomo(a) -> int:
    chart = nomo.multiply_nomograph()
    w = chart.solve(a.u, a.v)
    print("solve: %.4g * %.4g = %.6g" % (a.u, a.v, w))
    print()
    print(chart.chart_ascii(n_lines=9))
    print()
    print(chart.svg(n_lines=9))
    return 0


def _parse_bars(spec: str):
    bars = []
    for token in spec.split():
        try:
            n_s, amp_s, phase_s = token.split(",")
        except ValueError:
            raise SystemExit("bad bar %r: want n,amp,phase" % (token,)) from None
        bars.append((int(n_s), float(amp_s), float(phase_s)))
    if not bars:
        raise SystemExit("no bars given")
    return bars


def _cmd_fourier(a) -> int:
    bars = _parse_bars(a.bars)
    wave = fourier.bars_to_wave(bars, points=a.points)
    print("bars: %s" % (bars,))
    print(fourier.plot_ascii(wave, height=11))
    top = fourier.analyze(wave, top_k=min(5, len(bars)))
    print("recovered (top harmonics):")
    for n, amp, phase in top:
        print("  n=%d amp=%.4f phase=%.4f" % (n, amp, phase))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi.analog",
        description="Virtual analog workbench: patch-panel ODEs, "
        "nomographs, Fourier playground.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the damped-spring demo")
    r.add_argument("--m", type=float, default=1.0)
    r.add_argument("--c", type=float, default=0.5)
    r.add_argument("--k", type=float, default=4.0)
    r.add_argument("--x0", type=float, default=1.0)
    r.add_argument("--v0", type=float, default=0.0)
    r.add_argument("--t-end", type=float, default=10.0)
    r.add_argument("--dt", type=float, default=0.01)
    r.set_defaults(func=_cmd_run)

    pt = sub.add_parser("parts", help="Meccano parts list for the demo")
    pt.add_argument("--m", type=float, default=1.0)
    pt.add_argument("--c", type=float, default=0.5)
    pt.add_argument("--k", type=float, default=4.0)
    pt.add_argument("--x0", type=float, default=1.0)
    pt.add_argument("--v0", type=float, default=0.0)
    pt.set_defaults(func=_cmd_parts)

    n = sub.add_parser("nomo", help="log-scale nomograph for u*v=w")
    n.add_argument("--u", type=float, default=2.0)
    n.add_argument("--v", type=float, default=3.0)
    n.set_defaults(func=_cmd_nomo)

    f = sub.add_parser("fourier", help='stack bars, e.g. fourier "1,1.0,0 2,0.5,0"')
    f.add_argument("bars", help='"n,amp,phase" tokens separated by spaces')
    f.add_argument("--points", type=int, default=61)
    f.set_defaults(func=_cmd_fourier)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
