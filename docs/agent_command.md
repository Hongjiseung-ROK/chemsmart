# chemsmart agent — Command Taxonomy & Fine-tuning Dataset Specification

## 목적

이 문서는 `chemsmart agent ask "..."` 형식의 자연어 요청을 chemsmart 도구 호출 시퀀스(tool call JSON)로 변환하는 **로컬 LLM fine-tuning 데이터셋**을 구축하기 위한 사양서다.

학습된 모델은 cloud API 없이 on-premise(CPU-only, Ollama/llama.cpp)에서 동작하며, 연구소 보안 정책 하에서 Gaussian/ORCA HPC 워크플로우를 자동 구성하는 데 사용된다.

---

## 관련 소스 파일

데이터셋 구축 전 반드시 참조할 실제 파일 목록이다.

| 파일 경로 | 역할 |
|-----------|------|
| `chemsmart/agent/prompts/planner.md` | 플래너 시스템 프롬프트 — task→kind 매핑, rationale 품질 규칙, decline 규칙 전체 |
| `chemsmart/agent/prompts/tool_loop.md` | 도구 실행 루프 규칙 — 보수적 실행 원칙 |
| `chemsmart/agent/prompts/critic.md` | 제출 전 안전성 검증 규칙 |
| `chemsmart/agent/tools.py` | 18개 도구 구현 및 파라미터 정의 |
| `chemsmart/agent/registry.py` | 도구 레지스트리 — 등록된 도구 이름과 스키마 |
| `chemsmart/agent/cli.py` | CLI 진입점 (`ask`, `run`, `resume`, `sessions`, `tools`, `doctor`, `wizard`) |
| `chemsmart/agent/loop.py` | ToolLoop 실행 엔진 — 최대 12 model step, 32 tool call, 4 연속 오류 |
| `chemsmart/agent/permissions.py` | 권한 모드 (`read-only`, `accept-edits`, `bypass`, `plan`) |
| `chemsmart/agent/providers.py` | LLM 제공자 어댑터 (Anthropic, OpenAI-compatible) |
| `chemsmart/agent/services/conversation_memory.py` | 대화 메모리 — 슬롯(server, job_id, log_path 등) 지속 |
| `chemsmart/io/gaussian/__init__.py` | Gaussian 입력 파일 생성기 — 지원 functional, basis, solvent 목록 |
| `chemsmart/io/orca/__init__.py` | ORCA 입력 파일 생성기 — 지원 functional, basis, ab_initio 목록 |
| `chemsmart/jobs/gaussian/` | Gaussian job 구현 (`opt.py`, `ts.py`, `freq.py`, `sp.py`, `irc.py`, `scan.py`) |
| `chemsmart/jobs/orca/` | ORCA job 구현 (`opt.py`, `ts.py`, `freq.py`, `sp.py`, `irc.py`, `scan.py`) |
| `chemsmart/settings/templates/.chemsmart/gaussian/test.yaml` | Gaussian 프로젝트 설정 예시 |
| `chemsmart/settings/templates/.chemsmart/orca/test.yaml` | ORCA 프로젝트 설정 예시 |
| `examples/h2o.xyz` | 샘플 분자 구조 파일 |
| `docs/agent-quickstart.md` | 실제 실행 트랜스크립트 예시 |

---

## 도구 카탈로그 (Tool Catalogue)

`chemsmart/agent/tools.py` 및 `chemsmart/agent/registry.py` 기준. 학습 데이터의 모든 `tool` 필드는 이 이름만 사용한다.

### 핵심 화학 도구 (Core Chemistry Tools)

| 도구 이름 | 필수 파라미터 | 선택 파라미터 | 반환 타입 |
|-----------|-------------|-------------|----------|
| `build_molecule` | `filepath` (str) | `index` (str, default="-1") | Molecule |
| `recommend_method` | `task` (str) | `charge` (int), `multiplicity` (int), `atomic_numbers` (list[int]), `project_hint` (str) | dict |
| `build_gaussian_settings` | `functional` (str), `basis` (str) | `charge`, `multiplicity`, `solvent_model`, `solvent_id`, `heavy_elements`, `heavy_elements_basis`, `title`, `freq`, `numfreq`, `additional_opt_options_in_route`, `additional_route_parameters`, `scan_definition` | GaussianJobSettings |
| `build_orca_settings` | `basis` (str) | `functional`, `ab_initio`, `charge`, `multiplicity`, `solvent_model`, `solvent_id`, `dispersion`, `aux_basis`, `freq`, `numfreq`, `scf_tol`, `scf_algorithm`, `scf_maxiter`, `defgrid` | ORCAJobSettings |
| `build_job` | `kind` (JobKind), `molecule`, `settings` | `label` (str) | Job |
| `dry_run_input` | `job` | — | dict {inputfile, content} |
| `validate_runtime` | `job` | `server` | dict {ok, local_ok, local_issues} |
| `extract_optimized_geometry` | `job` | — | Molecule |

### 실행 도구 (Execution Tools)

| 도구 이름 | 필수 파라미터 | 반환 타입 |
|-----------|-------------|----------|
| `run_local` | `job` | dict {ok, returncode, stdout_path, stderr_path} |
| `submit_hpc` | `job` | dict {script_path, job_id} |

### HPC 검사 도구 (HPC Inspection Tools)

| 도구 이름 | 필수 파라미터 | 선택 파라미터 |
|-----------|-------------|-------------|
| `read` | `path` (str) | `start_line`, `limit` |
| `ssh_probe` | `server` (str) | — |
| `scheduler_query` | — | `server`, `job_id`, `scheduler` |
| `log_tail` | `server` (str), `path` (str) | `lines` (int) |

### 위자드 도구 (Wizard Tools)

`wizard_probe`, `wizard_write`, `wizard_verify`, `wizard_refresh`

---

## Job Kind 전체 목록

`planner.md` 기준. `build_job.kind`는 아래 12개 값 중 하나여야 한다.

```
gaussian.sp   gaussian.opt   gaussian.ts   gaussian.freq   gaussian.irc   gaussian.scan
orca.sp       orca.opt       orca.ts       orca.freq       orca.irc       orca.scan
```

### 자연어 → job kind 매핑 규칙 (planner.md 준수)

| 자연어 표현 | 올바른 kind | 금지 |
|------------|------------|------|
| optimize, optimization, geometry optimization | `*.opt` | — |
| transition state, TS, find TS | `*.ts` | `*.opt` 절대 금지 |
| IRC, reaction path, intrinsic reaction coordinate | `*.irc` | `*.opt` 절대 금지 |
| frequency, vibrational analysis (단독) | `*.freq` | — |
| single point, single-point, SP, energy | `*.sp` | `*.opt` 절대 금지 |
| scan, PES scan, potential energy scan | `*.scan` | — |
| opt+freq, opt and freq, optimize and frequency | `*.opt` + `freq=true` | `*.freq` 별도 금지 |

---

## 의도 분류 (Intent Classification)

플래너 출력의 `intent` 필드는 세 값 중 하나다.

| intent | 조건 | steps |
|--------|------|-------|
| `workflow` | 실행 가능한 도구 호출이 필요한 경우 | 1개 이상 |
| `advisory` | 구조 파일 없이 화학 조언만 필요한 경우 | `[]` (빈 배열) |
| `chitchat` | 인사, 감사, 능력 문의 등 비화학 대화 | `[]` (빈 배열) |

---

## 표준 워크플로우 시퀀스

`planner.md`에 명시된 표준 도구 호출 순서다. 데이터셋의 workflow 예시는 이 순서를 따른다.

### 기본 단일 계산
```
build_molecule → recommend_method → build_gaussian_settings / build_orca_settings
→ build_job → dry_run_input → validate_runtime
```

### Opt+Freq (단일 Gaussian 입력 파일)
```
build_molecule → recommend_method → build_gaussian_settings(freq=true)
→ build_job(kind=gaussian.opt) → dry_run_input → validate_runtime
```
> `gaussian.freq`를 별도 step으로 쓰는 것은 이미 최적화된 구조가 명시적으로 주어진 경우에만 허용.

### Gaussian Opt → ORCA SP (다중 프로그램 워크플로우)
```
build_molecule → recommend_method → build_gaussian_settings → build_job(kind=gaussian.opt)
→ dry_run_input → validate_runtime → run_local
→ extract_optimized_geometry(job="$step4")
→ build_orca_settings → build_job(kind=orca.sp, molecule="$step8")
→ dry_run_input → validate_runtime → submit_hpc
```

### HPC 제출 포함
```
... (기본 시퀀스) ... → validate_runtime → submit_hpc
```

---

## 데이터셋 출력 형식 (Training Format)

### JSONL 레코드 구조

각 학습 예시는 다음 형식의 JSONL 한 줄이다. OpenAI function-calling 형식과 호환된다.

```jsonl
{
  "messages": [
    {
      "role": "system",
      "content": "<planner.md 전체 내용을 그대로 사용>"
    },
    {
      "role": "user",
      "content": "<자연어 쿼리>"
    },
    {
      "role": "assistant",
      "content": "<JSON 문자열: steps/rationale/estimated_cost/intent 포함>"
    }
  ]
}
```

### assistant content 스키마

```json
{
  "steps": [
    {
      "tool": "<등록된 도구 이름>",
      "args": { "<파라미터 이름>": "<값 또는 $stepN 참조>" },
      "rationale": "<WHY를 설명하는 한 문장, 화학적 근거 포함>"
    }
  ],
  "rationale": "<전체 계획 요약 또는 advisory 답변>",
  "estimated_cost": "<Low / Medium / High 및 근거>",
  "intent": "workflow | advisory | chitchat"
}
```

### step 참조 규칙

- `build_molecule` 결과 전체 → `"$step1"`
- `recommend_method` 결과의 특정 필드 → `"$step2.functional"`, `"$step2.basis"`
- `build_job` 결과 전체 → `"$step4"` (build_job이 4번째인 경우)
- 인덱스는 1-based

---

## 데이터셋 카테고리 및 분배 계획

총 1,000개. 각 카테고리에 최소 분자 3종 이상, method 3종 이상이 포함되어야 한다.

### 카테고리 A: Gaussian 기본 계산 (180개)

**A-1. Gaussian SP** (60개)

트리거 표현: `single point`, `single-point`, `SP`, `energy calculation`

커버해야 할 변수:
- Functional: `B3LYP`, `PBE0`, `M06-2X`, `wB97X-D`, `CAM-B3LYP`
- Basis: `6-31G*`, `6-31G(d)`, `6-311+G(d,p)`, `def2-SVP`, `def2-TZVP`
- 분자: `H2O`, `NH3`, `CH4`, `ethanol`, `benzene`, `acetone`

예시 쿼리 패턴:
```
"single point calculation of h2o with b3lyp / 6-31g*, gaussian"
"gaussian SP on examples/h2o.xyz at PBE0/def2-SVP"
"energy calculation for ammonia using M06-2X/6-311+G(d,p)"
```

예시 출력 (steps 핵심 부분):
```json
{
  "steps": [
    {"tool": "build_molecule", "args": {"filepath": "examples/h2o.xyz"}, "rationale": "Load H2O geometry from the supplied XYZ file as the starting structure."},
    {"tool": "build_gaussian_settings", "args": {"functional": "B3LYP", "basis": "6-31G*", "title": "h2o_sp"}, "rationale": "B3LYP/6-31G* is cost-effective for this small closed-shell neutral organic single-point energy."},
    {"tool": "build_job", "args": {"kind": "gaussian.sp", "molecule": "$step1", "settings": "$step2", "label": "h2o_gaussian_sp"}, "rationale": "Single-point kind selected because only energy at fixed geometry is requested."},
    {"tool": "dry_run_input", "args": {"job": "$step3"}, "rationale": "Preview the generated input file before any execution to catch configuration errors early."},
    {"tool": "validate_runtime", "args": {"job": "$step3"}, "rationale": "Check local prerequisites so that a subsequent run_local or submit_hpc will not fail at launch."}
  ],
  "rationale": "Gaussian single-point energy on H2O at B3LYP/6-31G*: input generated and validated, no geometry relaxation performed.",
  "estimated_cost": "Low; small closed-shell molecule, SP only, typically seconds locally.",
  "intent": "workflow"
}
```

**A-2. Gaussian OPT** (60개)

트리거 표현: `optimize`, `geometry optimization`, `relax`

커버해야 할 변수:
- Functional/basis: A-1과 동일 + `HF/3-21G` (저수준 예비 최적화 패턴)
- 추가 opt 옵션: `tight`, `verytight`, `maxstep=8`
- `additional_route_parameters`: `scf=tight`, `nosymm`

**A-3. Gaussian Opt+Freq (freq=true)** (60개)

트리거 표현: `opt and freq`, `opt+freq`, `optimize and frequency`, `thermochemistry`

규칙: `build_gaussian_settings(freq=true)` + `build_job(kind=gaussian.opt)` — `gaussian.freq` 별도 사용 금지.

---

### 카테고리 B: ORCA 기본 계산 (180개)

**B-1. ORCA SP** (60개)

DFT 방식:
```json
{"tool": "build_orca_settings", "args": {"functional": "PBE0", "basis": "def2-TZVP"}}
```

Ab initio 방식 — `ab_initio` 사용, `functional=null`:
```json
{"tool": "build_orca_settings", "args": {"ab_initio": "DLPNO-CCSD(T)", "basis": "def2-TZVP", "functional": null, "aux_basis": "AutoAux"}}
```

커버해야 할 ab_initio 값: `HF`, `MP2`, `CCSD`, `DLPNO-CCSD(T)`

**B-2. ORCA OPT** (60개)

dispersion 포함 예시:
```json
{"tool": "build_orca_settings", "args": {"functional": "wB97X-D3", "basis": "def2-SVP"}}
```

**B-3. ORCA Opt+Freq** (60개)

`freq=true` 포함 ORCA 최적화.

---

### 카테고리 C: 전이상태 탐색 (100개)

**C-1. Gaussian TS** (50개)

트리거: `transition state`, `TS search`, `find TS`, `saddle point`

필수 규칙: `kind=gaussian.ts`. `gaussian.opt` 사용 절대 금지.

예시 쿼리:
```
"find the transition state for a Diels-Alder reaction at M06-2X/6-31G*"
"gaussian TS search for H2 + F → HF + H on examples/ts_guess.xyz at PBE0/def2-SVP"
```

Rationale 필수 요소: "TS optimization selected because the user requests a saddle point, not a minimum."

**C-2. ORCA TS** (50개)

---

### 카테고리 D: IRC 경로 (80개)

**D-1. Gaussian IRC** (40개)

트리거: `IRC`, `reaction path`, `intrinsic reaction coordinate`

필수 규칙: `kind=gaussian.irc`. TS 구조 파일이 입력이어야 함.

커버해야 할 변형:
- 방향 없음 (forward+reverse 자동)
- `forward` 전용
- `flat_irc=true`

예시 쿼리:
```
"run IRC from examples/ts.xyz at B3LYP/6-31G* Gaussian"
"Gaussian IRC forward direction only for ts_h2f.xyz at M06-2X/6-31G*"
```

**D-2. ORCA IRC** (40개)

ORCA IRC 특수 파라미터 포함: `direction` (both/forward/backward), `inithess`

---

### 카테고리 E: PES 스캔 (60개)

**E-1. Gaussian Scan** (40개)

트리거: `scan`, `PES scan`, `potential energy surface scan`

필수: `scan_definition` 파라미터. atom indices가 없으면 decline.

scan_definition 형식:
- 결합 거리(Bond): `"B 1 2 S 10 0.05"` (10 steps, 0.05 Å/step)
- 결합각(Angle): `"A 1 2 3 S 15 6.0"` (15 steps, 6°/step)
- 이면각(Dihedral): `"D 1 2 3 4 S 10 36.0"` (10 steps, 36°/step)

예시 쿼리:
```
"Gaussian dihedral scan of D 1 2 3 4 in examples/butane.xyz, B3LYP/6-31G*, 10 steps of 36 degrees"
"PES scan along bond B 4 17 in examples/mol.xyz at PBE0/def2-SVP, 8 steps of 0.1 angstrom"
```

Decline 예시 (indices 없음):
```
"scan the dihedral of ethanol at B3LYP/6-31G*"
→ steps: [], intent: advisory, rationale: "A Gaussian dihedral scan requires 1-based atom indices (e.g., D 1 2 3 4) and a step definition; please provide the four atom numbers that define the dihedral and the desired number of steps and step size."
```

**E-2. ORCA Scan** (20개)

---

### 카테고리 F: 용매 포함 계산 (80개)

트리거: `in water`, `with SMD`, `CPCM solvent`, `solvation`, `in THF`, `in methanol`

커버해야 할 조합:
- Gaussian: `solvent_model="smd"`, `solvent_id` 다양화 (water, methanol, acetonitrile, THF, toluene, DCM)
- ORCA: `solvent_model="cpcm"`, `solvent_model="smd"`

예시:
```json
{
  "tool": "build_gaussian_settings",
  "args": {
    "functional": "B3LYP", "basis": "6-31G*",
    "solvent_model": "smd", "solvent_id": "water",
    "charge": 0, "multiplicity": 1
  }
}
```

---

### 카테고리 G: 하전/개방각 계 (80개)

**G-1. 하전 분자 (Charged)** (40개)

트리거: `cation`, `anion`, `charge +1`, `charge -1`, `ionic`

필수 규칙: 음이온은 diffuse function 필요 → `6-31+G(d)` 또는 `aug-cc-pVDZ` 권장.

예시 쿼리:
```
"geometry optimization of NH4+ cation at B3LYP/6-31G*, gaussian"
"single point of formate anion (charge -1) at PBE0/6-31+G(d,p) Gaussian"
```

예시 args:
```json
{"functional": "PBE0", "basis": "6-31+G(d,p)", "charge": -1, "multiplicity": 1}
```

Rationale 필수 요소: "Diffuse functions (+) are added because the anion has more diffuse electron density."

**G-2. 개방각 계 (Open-shell)** (40개)

트리거: `radical`, `doublet`, `triplet`, `open-shell`, `unpaired electron`

예시 쿼리:
```
"UB3LYP/6-31G* doublet radical optimization of CH3 radical on examples/ch3.xyz"
"gaussian SP for O2 triplet state at PBE0/def2-TZVP"
```

예시 args:
```json
{"functional": "B3LYP", "basis": "6-31G*", "charge": 0, "multiplicity": 2}
```

Rationale 필수: "Multiplicity 2 (doublet) is set because the methyl radical has one unpaired electron."

---

### 카테고리 H: 다중 프로그램 복합 워크플로우 (80개)

**H-1. Gaussian Opt → ORCA SP** (50개)

`extract_optimized_geometry` 포함 전체 시퀀스.

예시 쿼리:
```
"optimize h2o.xyz at B3LYP/6-31G* with Gaussian, then run DLPNO-CCSD(T)/def2-TZVP single point with ORCA"
```

**H-2. TS → Freq 확인 → IRC** (30개)

예시 쿼리:
```
"find TS at M06-2X/6-31G* then verify with frequency and run IRC, gaussian, examples/ts_guess.xyz"
```

---

### 카테고리 I: Advisory (100개)

`steps: []`, `intent: "advisory"`.

**I-1. 방법론 추천** (50개)

예시 쿼리:
```
"What functional and basis set should I use for a Cope rearrangement TS?"
"Best method for dispersion-dominated pi-pi stacking?"
"When should I use DLPNO-CCSD(T) instead of DFT?"
```

Rationale: 화학적 근거 포함 상세 답변. 방법론 trade-off, 검증 단계 포함.

**I-2. 워크플로우 설계 조언** (30개)

예시:
```
"Should I optimize in gas phase first and then run SP with solvation?"
"What is the difference between gaussian.freq standalone and freq=True in optimization?"
```

**I-3. 오류/솔버 문제** (20개)

예시:
```
"Why does my SCF keep diverging?"
"What causes imaginary frequencies in a geometry optimization?"
```

---

### 카테고리 J: Decline / Edge Case (60개)

**J-1. 지원 불가 도구 요청** (20개)

`planner.md` decline rule: RESP, NCI, TDDFT, DIAS 등 미지원 도구.

예시:
```
"run RESP charge fitting for h2o.xyz"
→ steps: [], rationale: "RESP charge fitting is not supported by the registered tools..."
```

**J-2. 스캔 indices 누락** (15개)

예시 (위 E-1 decline 참고).

**J-3. 모호한 follow-up** (15개)

prior context 없이 모호한 참조:
```
"make it ORCA instead"
→ steps: [], intent: "advisory", rationale: "No prior workflow found in conversation history; please provide the molecule file and target method so I can build the ORCA equivalent."
```

**J-4. Off-topic (chitchat)** (10개)

`intent: "chitchat"`, steps: [].

예시:
```
"What's the weather today?" → 고정 거절 + chemsmart 소개
"Hello, what can you do?" → chitchat 응답
```

---

## 분배 요약표

| 카테고리 | 설명 | 수량 |
|---------|------|------|
| A-1 | Gaussian SP | 60 |
| A-2 | Gaussian OPT | 60 |
| A-3 | Gaussian Opt+Freq | 60 |
| B-1 | ORCA SP (DFT + ab initio) | 60 |
| B-2 | ORCA OPT | 60 |
| B-3 | ORCA Opt+Freq | 60 |
| C-1 | Gaussian TS | 50 |
| C-2 | ORCA TS | 50 |
| D-1 | Gaussian IRC | 40 |
| D-2 | ORCA IRC | 40 |
| E-1 | Gaussian Scan | 40 |
| E-2 | ORCA Scan | 20 |
| F | 용매 포함 계산 | 80 |
| G-1 | 하전 분자 | 40 |
| G-2 | 개방각 계 | 40 |
| H-1 | Gaussian Opt → ORCA SP | 50 |
| H-2 | TS → Freq → IRC | 30 |
| I | Advisory | 100 |
| J | Decline / Edge Case | 60 |
| **합계** | | **1,000** |

---

## 합성 데이터 생성 파이프라인

학습 데이터는 민감한 연구 데이터를 포함하지 않는 합성 예시로 구성한다.

### 단계 1: 쿼리 다양화 템플릿

각 카테고리에 대해 다음 변수를 조합해 쿼리를 생성한다.

```python
MOLECULES = ["H2O", "NH3", "CH4", "ethanol", "benzene", "acetone",
             "methanol", "CO2", "formic acid", "glycine"]
FILEPATHS = ["examples/h2o.xyz", "examples/mol.xyz", "examples/ts_guess.xyz"]

GAUSSIAN_FUNCTIONALS = ["B3LYP", "PBE0", "M06-2X", "wB97X-D", "CAM-B3LYP", "HF"]
ORCA_FUNCTIONALS     = ["B3LYP", "PBE0", "M06-2X", "wB97X-D3", "r2SCAN"]
ORCA_AB_INITIO       = ["HF", "MP2", "CCSD", "DLPNO-CCSD(T)"]

GAUSSIAN_BASIS = ["6-31G*", "6-31G(d)", "6-311+G(d,p)", "def2-SVP", "def2-TZVP", "6-31+G(d,p)"]
ORCA_BASIS     = ["def2-SVP", "def2-TZVP", "def2-TZVPP", "cc-pVDZ", "cc-pVTZ", "aug-cc-pVDZ"]

SOLVENTS = [("smd", "water"), ("smd", "methanol"), ("cpcm", "acetonitrile"),
            ("smd", "THF"), ("smd", "toluene"), ("smd", "DCM")]
```

### 단계 2: 출력 JSON 자동 검증

생성된 각 예시의 assistant content를 다음으로 검증한다.

1. `intent` ∈ {workflow, advisory, chitchat}
2. `steps[*].tool` ∈ 등록된 18개 도구 이름
3. `steps[*].args` — Pydantic 스키마 준수 여부 (실제 `registry.py` 스키마 사용)
4. `build_job.kind` ∈ 12개 canonical 값
5. step 참조 (`$stepN`) — 1-based, 이전 step 결과 타입 일치
6. `label` — 파일시스템 안전 문자만 (`[a-zA-Z0-9_\-]`)
7. ORCA ab initio 경우 `functional=null` 여부

### 단계 3: 생성 스크립트 실행 환경

```bash
# Colab Pro (A100) — 민감 데이터 없는 합성 데이터만 사용
python scripts/generate_dataset.py \
  --categories A B C D E F G H I J \
  --output data/finetune_chemsmart_1000.jsonl \
  --validate  # Pydantic 스키마 검증 포함
```

생성된 JSONL은 Google Drive에 저장 후 로컬 다운로드, lab 환경에서 QLoRA 훈련에 사용.

---

## 품질 체크리스트

각 예시를 데이터셋에 포함하기 전 아래를 확인한다.

- [ ] `tool` 이름이 `registry.py`에 등록된 이름과 정확히 일치
- [ ] `build_job.kind`가 12개 canonical 값 중 하나
- [ ] "single point" 쿼리에 `gaussian.opt` 사용 없음
- [ ] "transition state" 쿼리에 `gaussian.opt` 사용 없음
- [ ] ORCA correlated method(`DLPNO-CCSD(T)` 등)에 `ab_initio` 사용, `functional=null`
- [ ] Opt+Freq는 `build_gaussian_settings(freq=true)` + `build_job(kind=gaussian.opt)` 조합
- [ ] 각 step rationale이 "WHY"를 설명 (단순 "Build settings" 불가)
- [ ] 음이온 예시에 diffuse function 포함 근거 언급
- [ ] open-shell 예시에 multiplicity 근거 언급
- [ ] `label` 필드가 파일시스템 안전 문자만 포함
- [ ] Scan 예시에 `scan_definition` 파라미터 포함
- [ ] indices 없는 scan 요청은 decline으로 분류
- [ ] `$stepN` 참조가 올바른 step을 가리킴 (1-based)
- [ ] advisory 예시에 steps가 빈 배열 `[]`
- [ ] chitchat 예시에 화학/도구 관련 내용 없음

---

## 1차 / 2차 훈련 전략

1,000개 1차 훈련 후 실패 케이스를 분석해 2차 보강한다.

| 단계 | 데이터 | 목표 |
|------|--------|------|
| 1차 | 1,000개 (이 문서 기준) | 기본 tool chain 구성 및 포맷 학습 |
| 실패 분석 | 모델 오류 로그 수집 | 취약 카테고리 식별 |
| 2차 | +200~300개 (취약 카테고리 집중) | 정확도 보강 |

취약 카테고리 예상: IRC 특수 파라미터, ORCA double-hybrid, 다중 프로그램 워크플로우.
