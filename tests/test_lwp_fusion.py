"""Tests for levi.lwp.fusion — Intelligence Fusion Kernel (hermetic)."""

from levi.lwp.fusion import (
    FusionKernel,
    IntelligenceGenome,
    assess_risk,
    classify,
    compose,
    estimate_uncertainty,
    select_mix,
)


def test_classify_math():
    assert classify("calculate the quarterly budget total") == "math"


def test_classify_build():
    assert classify("build me a local checklist script") == "build"


def test_classify_research():
    assert classify("research the landscape of offline note tools") == "research"


def test_classify_judgment():
    assert classify("should I take this job offer?") == "judgment"


def test_classify_question_default():
    assert classify("what time is it") == "question"


def test_uncertainty_high_for_research():
    assert estimate_uncertainty("research unknown territory", "research") == "high"


def test_uncertainty_low_for_simple_math():
    assert estimate_uncertainty("add 2 and 3", "math") == "low"


def test_select_mix_math_leans_symbolic():
    mix = select_mix("math")
    assert mix["symbolic"] >= 0.9
    assert "generative" in mix


def test_select_mix_high_uncertainty_boosts_cognitive():
    low = select_mix("question", "low")
    high = select_mix("question", "high")
    assert high["cognitive"] >= low["cognitive"]


def test_select_mix_drops_unavailable_paradigms():
    caps = {
        "generative": True,
        "symbolic": True,
        "cognitive": True,
        "collective": False,
        "predictive": False,
        "evolutionary": False,
        "embodied": False,
        "human": True,
    }
    mix = select_mix("research", "low", caps)
    assert "collective" not in mix  # dropped honestly
    assert mix  # something remains


def test_genome_dominant_sorted():
    g = IntelligenceGenome(
        task="t",
        kind="math",
        uncertainty="low",
        mix={"symbolic": 1.0, "generative": 0.1, "cognitive": 0.6},
    )
    dom = g.dominant()
    assert dom[0] == "symbolic"
    assert "generative" not in dom  # below 0.5 threshold


def test_assess_risk_judgment_is_high():
    assert assess_risk("judgment", "low") == "high"
    assert assess_risk("question", "low") == "low"


def test_kernel_compose_plan_shape():
    plan = FusionKernel().compose("calculate the quarterly budget")
    genome = plan["genome"]
    assert genome["kind"] == "math"
    assert "symbolic" in genome["intelligence_mix"]
    assert plan["loop"][0] == "perceive"
    assert "policy_gate" in plan["loop"]
    assert plan["human_gate_required"] is False


def test_kernel_compose_judgment_needs_gate():
    plan = FusionKernel().compose("should I quit my job?")
    assert plan["human_gate_required"] is True


def test_kernel_explain_names_kind():
    text = FusionKernel().explain("calculate the quarterly budget")
    assert "math" in text
    assert "keeper approval" not in text  # low-risk path


def test_module_compose_convenience():
    plan = compose("research offline vector stores", constraints={"offline": True})
    assert plan["genome"]["constraints"] == {"offline": True}
    assert plan["genome"]["kind"] == "research"
