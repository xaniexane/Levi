"""Neuroplasticity + brain-region offline knowledge pack (LEVI atlas). Not medical advice."""

from __future__ import annotations
from typing import List, Tuple

NEURO_ATLAS: List[Tuple[str, List[str]]] = [
    # Neuroplasticity mechanisms
    (
        "Neuroplasticity: the nervous system's capacity to change structure and function with experience across the lifespan.",
        ["neuroplasticity", "neuroscience", "brain"],
    ),
    (
        "Hebbian learning shorthand: neurons that fire together wire together — correlated activity strengthens synapses.",
        ["neuroplasticity", "synapse", "learning"],
    ),
    (
        "Synaptic plasticity: lasting changes in synaptic strength, including LTP (potentiation) and LTD (depression).",
        ["neuroplasticity", "synapse", "LTP", "LTD"],
    ),
    (
        "Long-term potentiation (LTP): persistent increase in synaptic efficacy after high-frequency or associative stimulation.",
        ["LTP", "synapse", "hippocampus", "learning"],
    ),
    (
        "Long-term depression (LTD): lasting decrease in synaptic strength; important for refining circuits and flexibility.",
        ["LTD", "synapse", "neuroplasticity"],
    ),
    (
        "Spike-timing-dependent plasticity (STDP): order of pre/post spikes can determine potentiation vs depression.",
        ["STDP", "neuroplasticity", "synapse"],
    ),
    (
        "Structural plasticity: growth or pruning of spines, dendrites, and axons — anatomy follows use.",
        ["neuroplasticity", "structure", "dendrite"],
    ),
    (
        "Dendritic spines: small protrusions that host many excitatory synapses; volume changes track learning.",
        ["dendrite", "synapse", "learning"],
    ),
    (
        "Adult neurogenesis: new neurons in limited regions (notably hippocampus dentate gyrus in many mammals) — rates and function still researched in humans.",
        ["neurogenesis", "hippocampus", "plasticity"],
    ),
    (
        "Myelin plasticity: experience can alter myelination, changing conduction speed and circuit timing.",
        ["myelin", "white_matter", "plasticity"],
    ),
    (
        "Homeostatic plasticity: networks scale activity to stay stable — too much potentiation is balanced by adjustments.",
        ["homeostasis", "neuroplasticity", "network"],
    ),
    (
        "Metaplasticity: prior activity changes how easily synapses will potentiate or depress later.",
        ["metaplasticity", "synapse", "learning"],
    ),
    (
        "Critical periods: windows when certain circuits are especially malleable (e.g., aspects of sensory development).",
        ["critical_period", "development", "plasticity"],
    ),
    (
        "Sensitive periods: broader windows of heightened plasticity without absolute closure.",
        ["development", "plasticity", "learning"],
    ),
    (
        "Use-it-or-lose-it pruning: unused synapses are eliminated; practice protects pathways.",
        ["pruning", "learning", "habits"],
    ),
    (
        "Experience-dependent plasticity: changes driven by individual learning history, not only maturation.",
        ["plasticity", "learning", "experience"],
    ),
    (
        "Experience-expectant plasticity: development expects species-typical input (e.g., patterned light for vision).",
        ["development", "sensory", "plasticity"],
    ),
    (
        "BDNF (brain-derived neurotrophic factor): supports survival and plasticity of neurons; modulated by exercise and activity among other factors.",
        ["BDNF", "exercise", "plasticity"],
    ),
    (
        "Neuromodulators and plasticity: dopamine, acetylcholine, norepinephrine gate when learning sticks.",
        ["dopamine", "acetylcholine", "norepinephrine", "learning"],
    ),
    (
        "Dopamine prediction error: difference between expected and actual reward drives updating of value and habits.",
        ["dopamine", "learning", "basal_ganglia"],
    ),
    (
        "Acetylcholine and attention: cholinergic systems enhance cortical plasticity during focused states.",
        ["acetylcholine", "attention", "plasticity"],
    ),
    (
        "Norepinephrine and arousal: locus coeruleus activity modulates vigilance and memory under salience.",
        ["norepinephrine", "arousal", "locus_coeruleus"],
    ),
    (
        "Sleep and plasticity: slow-wave and REM stages support consolidation; chronic restriction impairs learning.",
        ["sleep", "memory", "plasticity"],
    ),
    (
        "Memory consolidation: fragile new traces stabilize over time; sleep and quiet rest help transfer/reorganize.",
        ["memory", "consolidation", "hippocampus"],
    ),
    (
        "Systems consolidation: hippocampal dependence of some memories lessens as cortex integrates patterns over time.",
        ["memory", "hippocampus", "cortex"],
    ),
    (
        "Reconsolidation: retrieved memories can become briefly labile and update — researched carefully in therapy contexts.",
        ["memory", "reconsolidation", "psychology"],
    ),
    (
        "Extinction learning: new inhibitory learning suppresses fear responses; not simple erasure of the old trace.",
        ["extinction", "fear", "amygdala", "learning"],
    ),
    (
        "Error-driven learning: mismatches between prediction and outcome are teaching signals for cortex and cerebellum.",
        ["learning", "cerebellum", "prediction"],
    ),
    (
        "Motor learning stages: cognitive → associative → autonomous; automaticity frees attention.",
        ["motor", "learning", "basal_ganglia"],
    ),
    (
        "Deliberate practice and plasticity: focused, feedback-rich difficulty drives change more than passive exposure.",
        ["practice", "learning", "plasticity"],
    ),
    (
        "Aerobic exercise and brain: associated with improved plasticity markers and hippocampal health in many studies.",
        ["exercise", "hippocampus", "BDNF"],
    ),
    (
        "Enriched environments: novelty, social complexity, and physical opportunity increase exploratory plasticity in animal models.",
        ["environment", "plasticity", "development"],
    ),
    (
        "Constraint-induced therapy idea: forcing use of an affected limb can drive cortical map reorganization after some injuries — clinical, supervised.",
        ["rehab", "plasticity", "motor_cortex"],
    ),
    (
        "Phantom limb and maps: cortical representation can reorganize after amputation; maps are competitive.",
        ["plasticity", "somatosensory", "maps"],
    ),
    (
        "Sensory substitution: with training, cortex can interpret novel input channels (e.g., tactile-to-visual devices).",
        ["plasticity", "sensory", "learning"],
    ),
    (
        "Bilingualism and control networks: managing languages engages control circuits; effects vary by age and proficiency.",
        ["language", "prefrontal", "plasticity"],
    ),
    (
        "Musician brains: auditory-motor coupling strengthens with years of practice — skill sculpts networks.",
        ["music", "motor", "auditory", "plasticity"],
    ),
    (
        "London taxi drivers study theme: navigational expertise linked to hippocampal structural differences — classic plasticity evidence.",
        ["hippocampus", "navigation", "plasticity"],
    ),
    (
        "Stroke recovery plasticity: surviving networks reorganize; intensity and timing of rehab matter — clinical domain.",
        ["stroke", "rehab", "plasticity"],
    ),
    (
        "Maladaptive plasticity: chronic pain, dystonia, or PTSD-related patterns can reflect learning that is harmful — needs professional care.",
        ["plasticity", "pain", "mental_health"],
    ),
    (
        "Addiction as learning: drugs hijack reward prediction circuits; habits entrench in basal ganglia loops.",
        ["addiction", "dopamine", "basal_ganglia"],
    ),
    (
        "Fear conditioning: amygdala rapidly associates cues with threat; prefrontal regulation can inhibit expression with safety learning.",
        ["amygdala", "fear", "prefrontal"],
    ),
    (
        "Habit loop neural: cue-routine-reward recruits striatum; goals start cortical, habits become more automatic.",
        ["habits", "striatum", "basal_ganglia"],
    ),
    (
        "Working memory limits: capacity is small; chunking and external notes extend effective cognition.",
        ["working_memory", "prefrontal", "learning"],
    ),
    (
        "Attention networks: alerting, orienting, executive control — partially separable systems.",
        ["attention", "networks", "prefrontal"],
    ),
    (
        "Default mode network (DMN): active in mind-wandering and self-reference; often anti-correlated with focused task networks.",
        ["DMN", "networks", "attention"],
    ),
    (
        "Salience network: detects important events and can switch between internal and external focus modes.",
        ["salience", "insula", "networks"],
    ),
    (
        "Central executive network: supports goal maintenance and manipulation of information.",
        ["executive", "prefrontal", "networks"],
    ),
    (
        "Predictive processing frame: brain constantly predicts sensory input; prediction errors update models.",
        ["prediction", "cortex", "learning"],
    ),
    (
        "Bayesian brain metaphor: perception as inference under uncertainty — priors plus evidence.",
        ["perception", "inference", "thinking"],
    ),
    (
        "Neuroinflammation caution: immune signaling affects mood and cognition; medical evaluation for persistent issues.",
        ["health", "brain", "inflammation"],
    ),
    (
        "Glucose and cognition: brain is energy-hungry; extreme restriction impairs clarity — fuel steadily.",
        ["nutrition", "brain", "health"],
    ),
    (
        "Hydration and attention: mild dehydration can worsen focus for some people.",
        ["health", "attention"],
    ),
    (
        "Chronic stress and plasticity: prolonged high cortisol is linked to hippocampal strain and weaker executive control.",
        ["stress", "hippocampus", "cortisol"],
    ),
    (
        "Acute stress and memory: moderate arousal can enhance encoding of salient events; extreme stress impairs.",
        ["stress", "memory", "amygdala"],
    ),
    (
        "Growth mindset neural angle: believing skills develop encourages practice behaviors that drive plasticity.",
        ["learning", "psychology", "plasticity"],
    ),
    (
        "Spaced practice neural: spacing allows consolidation between sessions; cramming produces fragile traces.",
        ["learning", "memory", "plasticity"],
    ),
    (
        "Interleaving practice: mixing related skills improves discrimination and long-term retention.",
        ["learning", "practice", "memory"],
    ),
    (
        "Retrieval practice: testing yourself strengthens memory more than re-reading — desirable difficulty.",
        ["learning", "memory", "hippocampus"],
    ),
    (
        "Dual coding: combining verbal and visual encodings creates richer retrieval routes.",
        ["learning", "memory", "education"],
    ),
    (
        "Sleep spindles and memory: spindle activity correlates with consolidation processes in research.",
        ["sleep", "memory", "plasticity"],
    ),
    (
        "REM and emotional memory: REM is implicated in processing emotional aspects of experience.",
        ["sleep", "REM", "emotion", "memory"],
    ),
    (
        "Naps and learning: short naps can help some forms of memory consolidation when schedule allows.",
        ["sleep", "memory", "learning"],
    ),
    (
        "Screen light and circadian: evening bright light can delay melatonin; dim evenings support sleep plasticity window.",
        ["sleep", "circadian", "health"],
    ),
    (
        "Exercise timing: regular activity supports plasticity; extreme overtraining without recovery can harm.",
        ["exercise", "plasticity", "health"],
    ),
    (
        "Meditation research theme: attention training associated with changes in control networks over time — effects vary.",
        ["meditation", "attention", "prefrontal"],
    ),
    (
        "Music training transfer: strongest gains are near trained skills; far transfer is often overstated.",
        ["music", "learning", "plasticity"],
    ),
    (
        "Video games and attention: action games can train certain attention skills; content and dose matter.",
        ["attention", "learning", "digital"],
    ),
    (
        "Social brain: interaction is a major driver of development; isolation stresses regulatory systems.",
        ["social", "development", "mental_health"],
    ),
    (
        "Attachment and regulation: early caregiving shapes stress systems; later relationships can still support change.",
        ["attachment", "stress", "plasticity"],
    ),
    (
        "Language acquisition: statistical learning of patterns; rich interactive input beats passive screens for infants.",
        ["language", "development", "learning"],
    ),
    (
        "Reading brain: literacy recycles visual circuitry for letter forms — cultural invention on biological hardware.",
        ["reading", "vision", "plasticity"],
    ),
    (
        "Numeracy networks: intraparietal regions often implicated in number sense; practice builds fluency.",
        ["math", "parietal", "learning"],
    ),
    (
        "Expertise chunking: experts perceive larger meaningful patterns — working memory looks bigger in domain.",
        ["expertise", "learning", "memory"],
    ),
    (
        "Cognitive reserve: education and engaging activity associated with resilience to pathology — correlation not guarantee.",
        ["aging", "brain", "health"],
    ),
    (
        "Healthy aging plasticity: learning remains possible; rate and ease change; novelty still matters.",
        ["aging", "plasticity", "learning"],
    ),
    (
        "Brain-derived myths: we use more than 10% of the brain; whole-brain networks are active in complex life.",
        ["myths", "neuroscience", "critical_thinking"],
    ),
    (
        "Left/right brain myth: personality is not simply left- vs right-brained; both hemispheres collaborate.",
        ["myths", "hemispheres", "critical_thinking"],
    ),
    (
        "Learning styles myth: matching teaching to preferred modality shows weak support; dual coding helps everyone.",
        ["myths", "education", "learning"],
    ),
    (
        "Neurofeedback caution: promising in research; quality and claims vary — seek qualified guidance.",
        ["tech", "brain", "health"],
    ),
    (
        "Brain training apps: near transfer common; far transfer to general IQ often limited — practice real skills.",
        ["learning", "tech", "critical_thinking"],
    ),
    (
        "Concussion protocol: rest from risk, gradual return, medical clearance — second impact is dangerous.",
        ["safety", "brain", "health"],
    ),
    (
        "Helmets and bikes: reduce risk of severe injury; not a license for recklessness.",
        ["safety", "brain"],
    ),
    (
        "Substance neurotoxicity: alcohol and other drugs can impair plasticity and memory — dose and pattern matter.",
        ["health", "brain", "safety"],
    ),
    (
        "Nicotine and attention: short-term focus effects with addiction and health costs — not a study strategy.",
        ["health", "attention"],
    ),
    (
        "Caffeine: can aid alertness; late use harms sleep-dependent plasticity.",
        ["health", "sleep", "attention"],
    ),
    (
        "Omega-3 and brain: dietary patterns matter; supplements are not magic — food pattern first.",
        ["nutrition", "brain", "health"],
    ),
    (
        "Mediterranean-style patterns: associated with better cognitive aging in observational research.",
        ["nutrition", "aging", "brain"],
    ),
    (
        "Social jetlag: weekend schedule shifts stress circadian alignment and learning readiness.",
        ["sleep", "circadian", "health"],
    ),
    (
        "Blue light tools: software dimming helps some; behavior (screens off) still primary.",
        ["sleep", "digital"],
    ),
    # Major brain regions
    (
        "Cerebral cortex: outer layer supporting perception, language, reasoning, and voluntary control — highly folded in humans.",
        ["cortex", "brain_regions", "neuroscience"],
    ),
    (
        "Frontal lobe: planning, control, personality expression, voluntary movement — executive hub.",
        ["frontal_lobe", "brain_regions", "executive"],
    ),
    (
        "Prefrontal cortex (PFC): goal maintenance, inhibition, working memory, social judgment.",
        ["prefrontal", "executive", "brain_regions"],
    ),
    (
        "Dorsolateral PFC: manipulation of information, planning, cognitive flexibility.",
        ["dlpfc", "prefrontal", "working_memory"],
    ),
    (
        "Ventromedial PFC: valuation, emotion-linked decisions, social affect regulation.",
        ["vmpfc", "decision", "emotion"],
    ),
    (
        "Orbitofrontal cortex: reward value updating, impulse-related evaluation, social reinforcers.",
        ["orbitofrontal", "reward", "decision"],
    ),
    (
        "Anterior cingulate cortex (ACC): conflict monitoring, error detection, motivation aspects.",
        ["ACC", "conflict", "attention"],
    ),
    (
        "Motor cortex (M1): primary map for voluntary movement output.",
        ["motor_cortex", "movement", "brain_regions"],
    ),
    (
        "Premotor and supplementary motor areas: action planning and sequencing before execution.",
        ["motor", "planning", "brain_regions"],
    ),
    (
        "Parietal lobe: spatial attention, body schema, integrating sensory streams.",
        ["parietal", "space", "attention"],
    ),
    (
        "Somatosensory cortex: touch and proprioception maps — adjacent body parts often adjacent on cortex.",
        ["somatosensory", "touch", "maps"],
    ),
    (
        "Temporal lobe: audition, aspects of memory and language, object recognition streams.",
        ["temporal", "auditory", "memory"],
    ),
    (
        "Superior temporal gyrus / auditory cortex: sound processing hierarchies.",
        ["auditory", "temporal", "brain_regions"],
    ),
    (
        "Wernicke's area (classic): language comprehension regions in temporal-parietal junction territory — models evolved.",
        ["language", "temporal", "Wernicke"],
    ),
    (
        "Broca's area (classic): speech production and grammar-related frontal regions — modern view is network-based.",
        ["language", "frontal", "Broca"],
    ),
    (
        "Occipital lobe: primary and higher visual processing.",
        ["occipital", "vision", "brain_regions"],
    ),
    (
        "Primary visual cortex (V1): first cortical stage of visual feature processing.",
        ["V1", "vision", "occipital"],
    ),
    (
        "Ventral visual stream: 'what' pathway toward temporal lobe for object identity.",
        ["vision", "temporal", "recognition"],
    ),
    (
        "Dorsal visual stream: 'where/how' pathway toward parietal lobe for spatial action.",
        ["vision", "parietal", "space"],
    ),
    (
        "Insula: interoception, disgust, salience, awareness of body states.",
        ["insula", "interoception", "emotion"],
    ),
    (
        "Hippocampus: episodic memory formation, spatial navigation, relational binding.",
        ["hippocampus", "memory", "navigation"],
    ),
    (
        "Dentate gyrus: hippocampal subfield involved in pattern separation of similar experiences.",
        ["dentate", "hippocampus", "memory"],
    ),
    (
        "CA1/CA3 hippocampal fields: pattern completion and sequence aspects of memory.",
        ["hippocampus", "memory", "learning"],
    ),
    (
        "Entorhinal cortex: interface between cortex and hippocampus; grid-cell research fame.",
        ["entorhinal", "navigation", "memory"],
    ),
    (
        "Amygdala: rapid threat and salience tagging; emotional learning of cues.",
        ["amygdala", "emotion", "fear"],
    ),
    (
        "Basal ganglia: action selection, habits, procedural skills, reward-based updating.",
        ["basal_ganglia", "habits", "motor"],
    ),
    (
        "Striatum (caudate/putamen/nucleus accumbens): key basal ganglia input for goals and habits.",
        ["striatum", "reward", "habits"],
    ),
    (
        "Nucleus accumbens: ventral striatum node in motivation and reinforcement learning.",
        ["nucleus_accumbens", "reward", "dopamine"],
    ),
    (
        "Globus pallidus and substantia nigra: basal ganglia output and dopamine source regions.",
        ["basal_ganglia", "dopamine", "motor"],
    ),
    (
        "Substantia nigra pars compacta: dopamine neurons critical for movement initiation; loss linked to Parkinson disease.",
        ["substantia_nigra", "dopamine", "motor"],
    ),
    (
        "Thalamus: relay and gate for sensory and motor signals to cortex; attention-related filtering.",
        ["thalamus", "relay", "attention"],
    ),
    (
        "Hypothalamus: homeostasis — hunger, thirst, temperature, circadian signals, autonomic drives.",
        ["hypothalamus", "homeostasis", "circadian"],
    ),
    (
        "Pituitary link: hypothalamic control of endocrine axes affects stress and growth hormones.",
        ["endocrine", "stress", "hypothalamus"],
    ),
    (
        "Cerebellum: timing, coordination, motor learning, prediction of sensory consequences of action.",
        ["cerebellum", "motor", "learning"],
    ),
    (
        "Brainstem: midbrain, pons, medulla — vital functions, cranial nerves, ascending arousal systems.",
        ["brainstem", "arousal", "vital"],
    ),
    (
        "Medulla oblongata: autonomic centers for breathing and heart-related control — medical emergency territory if injured.",
        ["medulla", "vital", "brainstem"],
    ),
    (
        "Pons: bridges signals; sleep and respiratory pattern involvement.",
        ["pons", "sleep", "brainstem"],
    ),
    (
        "Midbrain: superior/inferior colliculi for orienting; dopamine-rich zones.",
        ["midbrain", "orienting", "dopamine"],
    ),
    (
        "Locus coeruleus: main norepinephrine source; arousal and novelty response.",
        ["locus_coeruleus", "norepinephrine", "arousal"],
    ),
    (
        "Raphe nuclei: serotonin-rich brainstem groups modulating mood and many circuits.",
        ["serotonin", "raphe", "mood"],
    ),
    (
        "Corpus callosum: major fiber bundle connecting hemispheres — integration of lateralized processing.",
        ["corpus_callosum", "hemispheres", "white_matter"],
    ),
    (
        "White matter tracts: myelinated highways; lesions disconnect networks (disconnection syndromes).",
        ["white_matter", "networks", "myelin"],
    ),
    (
        "Gray matter: cell bodies and local circuits; cortical thickness studies track development and skill.",
        ["gray_matter", "cortex", "structure"],
    ),
    (
        "Ventricles and CSF: cerebrospinal fluid cushions and clears; medical if flow is blocked.",
        ["CSF", "health", "brain"],
    ),
    (
        "Blood-brain barrier: selective filter protecting brain chemistry — drugs differ in penetration.",
        ["BBB", "health", "pharmacology"],
    ),
    (
        "Neuroglia: astrocytes, oligodendrocytes, microglia support, myelinate, and immune-survey the brain.",
        ["glia", "myelin", "support"],
    ),
    (
        "Astrocytes: regulate synapse environment, blood flow coupling, transmitter clearance.",
        ["astrocyte", "synapse", "glia"],
    ),
    (
        "Microglia: immune cells of the brain; pruning and inflammatory roles.",
        ["microglia", "immune", "pruning"],
    ),
    (
        "Oligodendrocytes: produce CNS myelin — speed and synchrony of spikes.",
        ["oligodendrocyte", "myelin", "white_matter"],
    ),
    (
        "Mirror neuron debates: some neurons respond to both action and observation — interpretation remains nuanced.",
        ["mirror_neurons", "social", "motor"],
    ),
    (
        "Fusiform face area: region often specialized for faces; expertise also shapes ventral temporal areas.",
        ["fusiform", "vision", "face"],
    ),
    (
        "Place cells: hippocampal neurons coding location in an environment.",
        ["place_cells", "hippocampus", "navigation"],
    ),
    (
        "Grid cells: entorhinal neurons with hexagonal firing patterns supporting metric maps.",
        ["grid_cells", "entorhinal", "navigation"],
    ),
    (
        "Reward prediction pathways: VTA dopamine neurons broadcast teaching signals widely.",
        ["VTA", "dopamine", "learning"],
    ),
    (
        "Ventral tegmental area (VTA): midbrain dopamine source for mesolimbic and mesocortical paths.",
        ["VTA", "dopamine", "reward"],
    ),
    (
        "Prefrontal–amygdala balance: regulation of emotion depends on top-down and bottom-up dialogue.",
        ["prefrontal", "amygdala", "regulation"],
    ),
    (
        "Insula and addiction craving: interoceptive urge states involve insula networks in research.",
        ["insula", "addiction", "interoception"],
    ),
    (
        "Parietal neglect: right hemisphere damage can cause inattention to left space — clinical neurology.",
        ["parietal", "attention", "clinical"],
    ),
    (
        "Split-brain lessons: disconnecting callosum reveals specialized processing — ethics of classic cases matter.",
        ["corpus_callosum", "hemispheres", "history"],
    ),
    (
        "Broca aphasia pattern: effortful speech, relatively better comprehension — network not a single box.",
        ["language", "Broca", "clinical"],
    ),
    (
        "Wernicke aphasia pattern: fluent but impaired comprehension/meaning — network view modernized.",
        ["language", "Wernicke", "clinical"],
    ),
    (
        "Prosody and right hemisphere: emotional tone of speech often more right-lateralized.",
        ["language", "emotion", "hemispheres"],
    ),
    (
        "Executive dysfunction: frontal injury can spare IQ tests yet wreck planning and social judgment.",
        ["frontal", "executive", "clinical"],
    ),
    (
        "Working memory neural loop: PFC sustained activity plus parietal attention supports short-term hold.",
        ["working_memory", "prefrontal", "parietal"],
    ),
    (
        "Episodic vs semantic memory: episodes bind context (hippocampus-rich); facts become cortical semantic knowledge.",
        ["memory", "hippocampus", "cortex"],
    ),
    (
        "Procedural memory: skills in basal ganglia and cerebellum — knowing how vs knowing that.",
        ["memory", "basal_ganglia", "cerebellum"],
    ),
    (
        "Emotional memory: amygdala modulation makes charged events stick more strongly.",
        ["amygdala", "memory", "emotion"],
    ),
    (
        "Flashbulb memory: vivid feeling does not guarantee accuracy — confidence ≠ truth.",
        ["memory", "critical_thinking"],
    ),
    (
        "False memory risk: suggestion and imagination can create sincere errors — careful interviewing matters.",
        ["memory", "psychology", "ethics"],
    ),
    (
        "Attention bottleneck: limited capacity; multitasking is usually rapid switching with costs.",
        ["attention", "prefrontal", "productivity"],
    ),
    (
        "Inattentional blindness: focused attention can miss unexpected events in plain sight.",
        ["attention", "perception"],
    ),
    (
        "Change blindness: large visual changes go unnoticed without attention to the locus of change.",
        ["attention", "vision"],
    ),
    (
        "Cognitive load: excess split attention reduces learning; design instruction for limited working memory.",
        ["learning", "working_memory", "education"],
    ),
    (
        "Flow state description: high skill–challenge match, clear goals, absorbed attention — not constant.",
        ["attention", "psychology", "performance"],
    ),
    (
        "Mindfulness operational: repeated return of attention; trains noticing not emptying by force.",
        ["attention", "meditation", "regulation"],
    ),
    (
        "Rumination circuit risk: repetitive negative self-focus can strengthen mood-related patterns — interrupt with action/contact.",
        ["DMN", "mental_health", "psychology"],
    ),
    (
        "Exposure therapy principle: safety learning in presence of feared cues updates prediction — clinician-guided.",
        ["extinction", "anxiety", "learning"],
    ),
    (
        "CBT cognitive angle: thoughts influence emotion/behavior; testing beliefs is learning, not positive slogans.",
        ["psychology", "learning", "prefrontal"],
    ),
    (
        "Habit replacement: keep cue and reward, change routine — basal ganglia friendly strategy.",
        ["habits", "basal_ganglia", "behavior"],
    ),
    (
        "Implementation intentions: if-then plans link cues to actions and improve follow-through.",
        ["habits", "prefrontal", "goals"],
    ),
    (
        "Temptation bundling: pair wanted long-term behavior with immediate pleasant cue carefully.",
        ["habits", "motivation"],
    ),
    (
        "Ego depletion debate: willpower models contested; environment design still helps regardless of theory.",
        ["psychology", "habits", "critical_thinking"],
    ),
    (
        "Sleep stages cycle: NREM deep sleep and REM alternate; both contribute differently to restoration.",
        ["sleep", "brain", "health"],
    ),
    (
        "Adenosine and sleep pressure: builds with wake time; caffeine blocks receptors temporarily.",
        ["sleep", "adenosine", "caffeine"],
    ),
    (
        "Circadian SCN: suprachiasmatic nucleus is master clock entrained by light.",
        ["circadian", "hypothalamus", "SCN"],
    ),
    (
        "Melatonin signal: darkness-related hormone helping night physiology — not a sedative magic bullet alone.",
        ["sleep", "melatonin", "circadian"],
    ),
    (
        "Temperature and sleep: cool dark quiet supports onset for many people.",
        ["sleep", "health"],
    ),
    (
        "Learning before sleep: studying then sleeping beats all-nighters for durable memory.",
        ["sleep", "memory", "learning"],
    ),
    (
        "Motor skill overnight: offline gains after practice often appear after sleep.",
        ["sleep", "motor", "learning"],
    ),
    (
        "Infant sleep brain: high REM proportion; developmentally intense plasticity period.",
        ["development", "sleep", "plasticity"],
    ),
    (
        "Adolescent phase delay: natural later chronotype; school timing often mismatches biology.",
        ["circadian", "development", "sleep"],
    ),
    (
        "Neurodiversity framing: different neural wiring is variation; environments can enable or disable.",
        ["neurodiversity", "inclusion", "brain"],
    ),
    (
        "ADHD attention systems: regulation of attention and impulse involves fronto-striatal circuits — diagnosis is clinical.",
        ["ADHD", "attention", "prefrontal"],
    ),
    (
        "Autism spectrum: heterogeneous; sensory, social, and cognitive profiles vary — support not stereotype.",
        ["autism", "neurodiversity", "brain"],
    ),
    (
        "Monotropism link: deep attention tunnels can be a strength; forced rapid switching is costly.",
        ["monotropism", "attention", "neurodiversity", "levi"],
    ),
    (
        "Dyslexia networks: reading circuit differences; structured literacy helps many learners.",
        ["dyslexia", "reading", "learning"],
    ),
    (
        "Depression neural themes: networks of mood, reward, and control interact — treatment is multi-modal and professional.",
        ["depression", "mental_health", "networks"],
    ),
    (
        "Anxiety circuits: threat detection can be over-tuned; regulation skills and therapy retrain predictions.",
        ["anxiety", "amygdala", "prefrontal"],
    ),
    (
        "PTSD learning: strong threat associations; evidence-based therapies target safety learning — specialist care.",
        ["PTSD", "memory", "amygdala"],
    ),
    (
        "OCD loop theme: intrusive signals and compulsive reduction of anxiety can reinforce cycles — clinical treatment exists.",
        ["OCD", "basal_ganglia", "anxiety"],
    ),
    (
        "Parkinson circuit: dopamine loss in nigrostriatal path impairs movement initiation — medical neurology.",
        ["Parkinson", "dopamine", "motor"],
    ),
    (
        "Alzheimer pathology theme: memory networks vulnerable; risk reduction includes vascular health and sleep — not guaranteed prevention.",
        ["aging", "memory", "health"],
    ),
    (
        "Multiple sclerosis: immune attack on myelin disrupts conduction — medical specialty care.",
        ["myelin", "white_matter", "health"],
    ),
    (
        "Epilepsy: abnormal synchronized firing; triggers individual; medical management essential.",
        ["epilepsy", "cortex", "health"],
    ),
    (
        "Migraine network: sensory processing and brainstem involvement; triggers vary — medical guidance.",
        ["migraine", "pain", "brain"],
    ),
    (
        "Chronic pain plasticity: central sensitization can amplify signals; multidisciplinary care often needed.",
        ["pain", "plasticity", "health"],
    ),
    (
        "Placebo neural: expectation recruits endogenous opioid and other systems — real physiology, not 'fake'.",
        ["placebo", "expectation", "brain"],
    ),
    (
        "Nocebo: negative expectation can worsen symptoms — framing of risk matters ethically.",
        ["nocebo", "expectation", "ethics"],
    ),
    (
        "Mirror therapy rehab: visual feedback can ease some phantom pain — under clinical protocols.",
        ["rehab", "plasticity", "pain"],
    ),
    (
        "Brain-computer interfaces: decode intent from signals; ethics of privacy and agency are active issues.",
        ["BCI", "tech", "ethics"],
    ),
    (
        "fMRI limits: indirect blood-flow signal; reverse inference of thoughts from blobs is often overclaimed.",
        ["fMRI", "methods", "critical_thinking"],
    ),
    (
        "EEG: electrical rhythms; good time resolution, coarser spatial maps.",
        ["EEG", "methods", "brain"],
    ),
    (
        "Lesion method history: deficits after damage map function — modern ethics limit such harm.",
        ["methods", "history", "brain_regions"],
    ),
    (
        "Single-cell recording: animal research revealed place and grid cells — translational caution required.",
        ["methods", "navigation", "ethics"],
    ),
    (
        "Optogenetics: light-controlled neurons in research animals — precise causal tools, not consumer toys.",
        ["methods", "research", "ethics"],
    ),
    (
        "Connectome idea: mapping wiring diagrams; function still needs dynamics, not only cables.",
        ["networks", "connectome", "brain"],
    ),
    (
        "Small-world brain: local clusters with long-range shortcuts — efficient yet vulnerable hubs.",
        ["networks", "graph", "brain"],
    ),
    (
        "Hub regions: highly connected nodes; damage can cascade widely.",
        ["networks", "clinical", "brain"],
    ),
    (
        "Developmental plasticity peak: childhood high malleability; adulthood retains targeted change with practice.",
        ["development", "plasticity", "learning"],
    ),
    (
        "Sensitive caregiving: co-regulation teaches nervous systems safety — foundation for later learning.",
        ["development", "attachment", "regulation"],
    ),
    (
        "Serve-and-return: contingent adult responses build language and social circuits in early years.",
        ["development", "language", "social"],
    ),
    (
        "Toxic stress: prolonged activation without support harms developing systems — policy and care matter.",
        ["stress", "development", "health"],
    ),
    (
        "Play and brain: exploratory play builds flexible behavior and social skill — not optional fluff.",
        ["development", "learning", "play"],
    ),
    (
        "Adolescent pruning: synaptic refinement continues; risk-taking partly reflects still-maturing control networks.",
        ["development", "adolescence", "prefrontal"],
    ),
    (
        "Identity formation neural-social: peers and status strongly shape adolescent learning priorities.",
        ["development", "social", "learning"],
    ),
    (
        "Adult skill acquisition: slower than child sensory critical periods but robust with deliberate practice.",
        ["learning", "plasticity", "adult"],
    ),
    (
        "Transfer of learning: near transfer reliable; far transfer rare — train the real task.",
        ["learning", "education"],
    ),
    (
        "Desirable difficulties: spacing, testing, variation feel harder and produce stronger learning.",
        ["learning", "memory", "education"],
    ),
    (
        "Generation effect: producing answers yourself beats passive recognition for memory.",
        ["learning", "memory"],
    ),
    (
        "Hypercorrection effect: high-confidence errors, once corrected, can stick well — feedback matters.",
        ["learning", "memory"],
    ),
    (
        "Interleaved arts/science: switching contexts can improve long-term discrimination of concepts.",
        ["learning", "education"],
    ),
    (
        "Gesture and learning: hand movement can support math and language encoding for some learners.",
        ["learning", "motor", "education"],
    ),
    (
        "Exercise breaks: brief movement can restore attention during long study blocks.",
        ["attention", "exercise", "learning"],
    ),
    (
        "Nature exposure: associated with attention restoration for many people — useful study breaks.",
        ["attention", "health", "environment"],
    ),
    (
        "Social learning: mirror and model others; communities of practice accelerate skill.",
        ["learning", "social"],
    ),
    (
        "Teaching-to-learn: explaining forces organization of knowledge — stronger traces.",
        ["learning", "memory", "education"],
    ),
    (
        "Note-taking generative: summarizing in own words beats transcribing slides.",
        ["learning", "pkm"],
    ),
    (
        "Concept maps: externalize relations; supports schema building in cortex-friendly ways.",
        ["learning", "memory", "education"],
    ),
    (
        "Schema theory: new info sticks when linked to existing organized knowledge.",
        ["memory", "learning", "schema"],
    ),
    (
        "Levels of processing: deeper semantic encoding outperforms shallow rote for long-term memory.",
        ["memory", "learning"],
    ),
    (
        "Encoding specificity: cues present at learning help retrieval — match contexts when possible.",
        ["memory", "learning"],
    ),
    (
        "State-dependent effects: internal state can cue memory; still prefer multiple retrieval routes.",
        ["memory", "psychology"],
    ),
    (
        "Prospective memory: remembering to act later relies on cues and planning — external reminders help.",
        ["memory", "prefrontal", "productivity"],
    ),
    (
        "Metacognition: monitoring what you know prevents illusion of mastery after highlighting.",
        ["learning", "prefrontal", "education"],
    ),
    (
        "Calibration of confidence: practice estimating accuracy; overconfidence is common.",
        ["thinking", "metacognition"],
    ),
    (
        "Cognitive offloading: writing and tools free working memory — legitimate strategy, not cheating life.",
        ["working_memory", "productivity", "pkm"],
    ),
    (
        "LEVI offline brain: neuro notes are educational frames for local SI — not diagnosis or treatment plans.",
        ["levi", "neuroscience", "ethics"],
    ),
]


def neuro_units():
    return list(NEURO_ATLAS)
