# HPC test-cluster provider survey for chemsmart agent

## 1. Executive summary

- Recommended cheapest free start: (1) KISTI Nurion if a Korean academic/GRI route is available, because it already documents PBS scheduling and publicly lists Gaussian 16 on-system; (2) KISTI Neuron if GPU-heavy ORCA/auxiliary work matters more than Gaussian; (3) UNIST/GIST regional centers if local affiliation exists and queue friction matters more than absolute scale. [K1][K2][K3][K4][K5][K6][G1][G2][G3][U1][U2][U3][U4]
- Recommended paid path: (1) Oracle Cloud HPC for budget-sensitive Slurm + RDMA builds with straightforward public pricing and standard SSH/bastion patterns; (2) AWS ParallelCluster for the most mature chemistry/HPC docs and predictable Slurm head-node workflow; (3) Google Cloud Cluster Toolkit for clean Slurm automation if you prefer GCP primitives over a managed HPC control plane. [OCI1][OCI2][OCI3][AW1][AW2][AW3][AW4][GCP1][GCP2][GCP3]
- Hard blockers for a Korea-based PI: ACCESS-CI and CloudBank are effectively U.S.-PI/U.S.-researcher programs; EuroHPC regular access is for EU Member/Participating/associated-country entities, so direct KR-PI fit is weak without a qualifying partner. [A1][A2][CB1][CB2][E1][E2]
- Gaussian posture is the first filter: Nurion is the only surveyed option where public docs explicitly show Gaussian 16 on the system; most public clouds are safest to treat as BYOL/self-install only, and many SaaS/GPU clouds do not publish a clear Gaussian stance at all. ORCA is easier because official binaries are free for academic users, though site policy still matters. [K5][Q1][Q2]
- Avoid for first chemsmart validation unless forced by existing credits: marketplace/GPU-rental platforms (Vast.ai, RunPod, TensorDock) and opaque-sales HPCaaS (Rescale) add avoidable scheduler, licensing, or billing ambiguity for a simple Linux-SSH + shared-filesystem chemistry cluster. [RUN1][RUN2][VAST1][TD1][TD2][TD3][RES1][RES2][RES3][RES4]

## 2. chemsmart requirements recap

chemsmart wants a Linux SSH entry point, a scheduler the wizard already knows (SLURM, SGE/UGE, PBS/Torque, or LSF), shared scratch + home storage, and a realistic path to Gaussian g16 and/or ORCA. For this survey, Gaussian stance is treated as a first-class go/no-go item; KR onboarding friction (eligibility, cards, invoice path, sales gating) is treated as a cost, not an afterthought.

Checklist:

- [x] Linux SSH head/login node
- [x] Scheduler in chemsmart wizard set: SLURM / SGE / UGE / PBS / Torque / LSF
- [x] Shared scratch + home filesystem
- [x] Gaussian g16 preferred; ORCA acceptable
- [x] Free allocation path and/or pay-as-you-go path
- [x] Korea-based user fit called out explicitly

## 3. Comparison matrix

| Provider | Free tier/credit | Pricing | Scheduler | Gaussian | ORCA | Storage & egress | KR onboarding | Min spend/lock-in | Reputation flags | chemsmart fit (1–5) |
|---|---|---|---|---|---|---|---|---|---|---:|
| ACCESS-CI | Free to awarded users; Explore/Discover/Accelerate via ACCESS Credits, Maximize on annual cycle; U.S.-based PI required. [A1][A2][A4] | No user bill. [A4] | Resource-specific; ACCESS resources commonly expose Slurm (example: Expanse). [A3] | BYOL only; no public ACCESS-wide Gaussian module policy found. [Q1][unverified] | User-installable for academic users. [Q2] | Shared HPC storage varies by site; Expanse shows Lustre + node-local SSD scratch. [A3] | Poor for KR PI; U.S.-based PI gate. [A1] | No spend, strong eligibility lock. [A1] | Great hardware, but Korea fit is weak. [A1] | 2 |
| EuroHPC JU / PRACE legacy | EuroHPC access is free for eligible open-R&D users; regular access is continuously open; PRACE pages are legacy/archive only. [E1][E2][E5] | No public user bill for awarded projects. [E1] | Site-specific; representative EuroHPC systems LUMI and Leonardo use Slurm. [E3][E4] | No public EuroHPC-wide Gaussian policy; assume BYOL/site-by-site approval only. [Q1][unverified] | User-installable for academic users if host permits. [Q2] | Shared HPC filesystems on host systems; details are site-specific. [E3][E4] | Weak for direct KR PI unless a qualifying European entity leads/hosts the access path. [E1] | No spend, but legal-entity eligibility lock. [E1] | Strong hardware, weak direct eligibility from Korea. [E1] | 2 |
| KISTI Nurion | National R&D support plus paid service; 2026 R&D innovation call exists and paid-use process is published. [K1][K2] | Paid usage process supports bank transfer/card; calculator published. [K1] | PBS. [K3] | Public docs list Gaussian16 and Gaussian16 Linda on-system. [K3] | User-installable likely; no public site module found. [Q2][unverified] | Parallel filesystem, burst buffer, archive, DTN; login via SSH. [K3][K4] | Strong if you can qualify through Korean academic/GRI channels. [K1][K2] | Low contractual lock; institutional paperwork/OTP/account flow required. [K1][K4] | Best-publicly-documented Gaussian fit in survey. [K3] | 5 |
| KISTI Neuron | R&D support plus paid use via KISTI process. [K1][K2] | Paid usage process supports bank transfer/card. [K1] | Slurm. [K5] | No public Gaussian module found. [Q1][unverified] | User-installable for academic users. [Q2] | Lustre-based shared storage; jobs submitted from scratch; Jupyter integrates with Slurm. [K5][K6] | Strong if you can qualify through Korean academic/GRI channels. [K1][K2] | Low vendor lock; institutional account + OTP flow. [K1] | Good domestic option, but Gaussian posture is unclear. [K5][Q1] | 4 |
| KAIST KCloud | Institutional internal cloud; no public free-credits program found in reviewed pages. [KA1][KA2] | Internal VM-style service; no public HPC cluster price catalog reviewed. [KA1][unverified] | No public batch scheduler found in reviewed KCloud docs. [KA1][unverified] | BYOL/self-install only if license permits. [KA1][Q1] | User-installable. [Q2] | VM/network/security-group workflow; SSH now gated by KCLOUDVPN/NAT path. [KA1][KA2] | Good only with KAIST/internal sponsorship or approved external access. [KA2] | Access gating via VPN/account request for outsiders. [KA2] | More campus cloud than ready HPC cluster. [KA1][KA2] | 2 |
| SNU CloudFirst | Discount/support path for SNU researchers using major clouds; not a free national HPC allocation. [S1] | Public note says AWS and other major cloud MOUs with ~15%–21% support/discount. [S1] | Scheduler depends on chosen cloud; SNU page is cloud-procurement support, not a cluster product. [S1] | BYOL on chosen cloud. [Q1][S1] | User-installable on chosen cloud. [Q2][S1] | Depends on selected CSP. [S1] | Good if you are an SNU lab; otherwise not directly usable. [S1] | Lock-in is to chosen CSP + campus procurement path. [S1] | Helpful procurement channel, not a turnkey chemsmart cluster. [S1] | 2 |
| GIST Super Computing Center | Regional shared infrastructure with application/contract flow; not a public self-serve free tier. [G1][G3] | Published usage guidance and pricing page. [G1][G3] | Public pages show Slurm-backed HPC-AI nodes and a global scheduler/file-system stack. [G2][G4] | No public Gaussian module found. [Q1][unverified] | User-installable for academic users if site policy allows. [Q2][unverified] | Shared cluster/data-lake style infrastructure; public pages mention global file system. [G2][G4] | Good if GIST/regional access is realistic. [G1] | Application + contract + possible fee path. [G1][G3] | Better regional fit than overseas grant programs; software stack for chemistry is unclear. [G1][G2] | 3 |
| UNIST Supercomputing Center | Campus/regional resource; application form and usage-fee guide published. [U1][U3] | Usage-fee guide referenced publicly; not self-serve hourly cloud. [U3] | Batch-processing support is public; exact scheduler not stated on the landing pages reviewed. [U3][unverified] | No public Gaussian module found. [Q1][unverified] | User-installable for academic users if policy allows. [Q2][unverified] | SSH login nodes, Lustre, local storage; multiple Linux clusters. [U1][U2][U4] | Good if UNIST/regional affiliation exists. [U1][U3][U5] | Institutional application/document flow. [U3] | Real cluster with SSH and shared storage, but public scheduler/software detail is lighter than KISTI. [U1][U2][U3] | 3 |
| KREONET | Not a compute allocation; research network/service layer. [KR1][KR2] | Not a compute-pricing product. [KR1] | Not a scheduler provider. [KR1] | Absent. [KR1] | Absent. [KR1] | Network/Science-DMZ/data-transfer value, not compute. [KR2] | Useful adjunct in Korea, not a cluster. [KR1][KR2] | N/A for cluster procurement. [KR1] | Out of scope for actual chemsmart compute. [KR1][KR2] | 1 |
| CloudBank | Service-based access to public clouds; now available via ACCESS/NAIRR for U.S.-based researchers and educators. [CB1][CB2] | Pay-by-use charge model on commercial clouds. [CB1] | Depends on underlying cloud/service. [CB1] | BYOL on underlying cloud. [Q1][CB1] | User-installable on underlying cloud. [Q2][CB1] | Depends on underlying cloud; CloudBank adds spend controls. [CB1] | Poor for direct KR PI; U.S.-based researcher framing. [CB2] | No large lock-in, but strong eligibility lock. [CB2] | Good control plane, wrong geography for Korea-first use. [CB1][CB2] | 2 |
| Google Cloud for Researchers | Proposal-based credits up to $5,000 for academic research. [GR1] | Credit-funded GCP consumption. [GR1] | Whatever you build on GCP; Slurm supported through Cluster Toolkit. [GCP1] | BYOL/self-install. [Q1] | User-installable. [Q2] | Standard GCP block/object/egress model. [GCP3] | Decent if your institution can apply; still proposal-driven, not instant. [GR1] | Limited credit amount; then normal GCP billing. [GR1][GCP3] | Best as a short pilot, not as a long home. [GR1][GCP1] | 3 |
| AWS Cloud Credit for Research | Proposal-based research credits for finite projects. [AWSR1] | Credit-funded AWS consumption. [AWSR1] | Whatever you build on AWS; ParallelCluster supports Slurm and AWS Batch. [AW1] | BYOL/self-install. [Q1] | User-installable. [Q2] | Standard EC2/EBS/data-transfer model. [AW3][AW4] | Possible from Korea with institutional email, but still application-based and not guaranteed. [AWSR1] | Limited credits; after that normal AWS billing. [AWSR1][AW3] | Useful if awarded, but not a guaranteed starting point. [AWSR1] | 3 |
| Azure Research Credits | Proposal-based research credits. [AZR1] | Credit-funded Azure consumption. [AZR1] | Whatever you build on Azure; CycleCloud supports major HPC schedulers. [AZ1] | BYOL/self-install. [Q1] | User-installable. [Q2] | Standard VM/storage/egress model. [AZ3][AZ4] | Viable if your institution can apply; still proposal/sponsorship gated. [AZR1] | Limited credits; then regular Azure billing. [AZR1][AZ3] | Good for short proof-of-concept only. [AZR1][AZ1] | 3 |
| Oracle for Research | Free cloud credits for data-driven research. [ORR1] | Credit-funded OCI consumption. [ORR1] | Whatever you build on OCI; Slurm is the standard OCI HPC pattern. [OCI2] | BYOL/self-install. [Q1] | User-installable. [Q2] | Standard OCI storage/network model. [OCI1][OCI2] | Reasonable if awarded; still application-based. [ORR1] | Limited credits; then normal OCI billing. [ORR1][OCI1] | Strong paid follow-on path if credits land. [ORR1][OCI2] | 4 |
| AWS ParallelCluster | No free tier beyond generic credits/free-trial constructs. [AW3][AWSR1] | EC2 + EBS + egress; Spot supported through EC2. [AW1][AW3][AW4] | Slurm or AWS Batch; SSH to head node documented. [AW1][AW2] | BYOL/self-install only. [Q1][AW2] | User-installable. [Q2][AW2] | Shared storage is configurable (for example EFS/FSx/Lustre) but separately billed; egress billed per AWS norms. [AW3][AW4][unverified-config-choice] | Strong self-serve from Korea if you already have AWS billing. [AW3] | Pure PAYG unless you add reservations/commitments. [AW3][AW4] | Best-documented mainstream option. [AW1][AW2] | 5 |
| Azure CycleCloud | No dedicated free tier; research credits can offset. [AZR1][AZ3] | VM + storage + egress; Spot VMs available. [AZ3][AZ4] | Official templates for PBS Pro, LSF, Grid Engine, Slurm, HTCondor; SSH/admin access documented. [AZ1][AZ2] | BYOL/self-install only. [Q1] | User-installable. [Q2] | NFS/BeeGFS templates and Azure storage/network pricing apply. [AZ1][AZ3] | Strong self-serve if Azure billing is already set up. [AZ3] | PAYG; enterprise controls available. [AZ3][AZ4] | Scheduler flexibility is excellent; chemistry examples are thinner than AWS. [AZ1][AZ2] | 4 |
| Google Cloud Cluster Toolkit | No dedicated free tier; research credits can offset. [GR1][GCP3] | Compute + storage + egress; Spot/discount options depend on GCE primitives. [GCP3] | Slurm quickstart documented; standard GCE SSH. [GCP1][GCP2] | BYOL/self-install only. [Q1] | User-installable. [Q2] | Shared filesystem choice is up to deployment pattern; normal GCP storage/egress pricing applies. [GCP1][GCP3] | Strong self-serve if GCP billing is ready. [GCP2][GCP3] | PAYG; no mandatory long contract. [GCP3] | Clean automation, fewer chemistry-specific guardrails than AWS. [GCP1][GCP2] | 5 |
| Oracle Cloud HPC | No dedicated free tier for real HPC; Oracle for Research can offset. [ORR1][OCI1] | Public OCI pricing; standard PAYG. [OCI1] | Slurm-centered HPC guidance; SSH via Bastion/managed SSH patterns. [OCI2][OCI3] | BYOL/self-install only. [Q1] | User-installable. [Q2] | Block/file/object options; standard OCI pricing. [OCI1][OCI2] | Good from Korea if card/invoice path is acceptable; public docs include card/bank-transfer patterns in adjacent programs. [OCI1][OCI3][inference] | PAYG; commitment optional, not required. [OCI1] | Good budget/perf story, but Oracle operational ergonomics still need hands-on validation. [OCI1][OCI3] | 5 |
| Rescale | No free self-serve research tier found in reviewed pages. [RES1][RES4] | Quote/demo-led; no public per-hour catalog found in reviewed pages. [RES1][RES4] | Works with Slurm and other schedulers; can integrate with existing schedulers. [RES2] | Public materials mention Gaussian, but licensing path is not public. [RES3][unverified] | Likely supported via app workflows; exact path depends on platform/licensing. [RES1][unverified] | Multi-cloud storage/data management are part of platform pitch; exact charges opaque publicly. [RES2][unverified] | Korea onboarding likely sales-led rather than instant self-serve. [RES4][inference] | High lock-in to platform workflow and pricing opacity. [RES1][RES4] | Powerful, but too opaque for a cheap first test cluster. [RES1][RES2][RES3][RES4] | 2 |
| Penguin POD | No free tier found. [POD1] | Public pricing datasheet exists but is dated; current commercial terms likely via sales. [POD1][POD2][unverified-old] | HPC cloud positioning; public docs imply traditional HPC environment, but reviewed pages do not explicitly state current scheduler. [POD1][POD3][unverified] | No public Gaussian statement found. [Q1][unverified] | Additional software install can be requested by email. [POD3] | Corresponding storage system per compute queue in public datasheet. [POD2][unverified-old] | Sales-led; Korea fit depends on contracting, not instant cards. [POD1][inference] | Likely commercial contract. [POD1][POD2] | Interesting bare-metal HPC, but dated public pricing/software info. [POD1][POD2][POD3] | 3 |
| Hyperstack | No free tier found. [HS1] | Public on-demand, reserved, and spot pricing; ingress/egress listed free. [HS1][HS2] | No public managed HPC scheduler found; user-managed VMs only in reviewed pages. [HS1][unverified] | BYOL/self-install only. [Q1][HS1] | User-installable. [Q2][HS1] | SSVs, snapshots, public IP charges; egress/ingress listed free. [HS1] | Self-serve and cheaper than hyperscalers; Korea card path not separately documented. [HS1][inference] | PAYG or reservation. [HS1] | Cheap GPU cloud, but weak chemsmart scheduler story. [HS1][HS2] | 2 |
| Crusoe Cloud | No free tier found. [CR1] | Minute-billed on-demand/spot/reserved; no ingress/egress charge per pricing FAQ. [CR1] | Managed Slurm with documented login nodes. [CR2] | BYOL/self-install only. [Q1][CR2] | User-installable. [Q2][CR2] | Storage tab in pricing; no network ingress/egress charge per pricing page. [CR1] | Self-serve/public pricing exists; Korea path still likely USD card + new vendor. [CR1][inference] | PAYG or reserved commitments. [CR1] | Better than GPU-only marketplaces because Slurm exists, but chemistry references are thin. [CR1][CR2] | 4 |
| Nebius AI Cloud | Promo-code credits exist, but no standing free tier. [NEB1] | Public PAYG pricing, commitment discounts, card or bank-transfer options; first payment minimum $25. [NEB1][NEB3] | Managed Slurm/Soperator and managed Slurm positioning. [NEB2][NEB4] | BYOL/self-install only. [Q1] | User-installable. [Q2] | Block disks, shared filesystems, object storage; PAYG storage billed separately. [NEB3] | Better than many startups because pricing and payment methods are explicit; still new vendor/regions. [NEB1] | Low minimum entry, optional commitments. [NEB1][NEB3] | Serious contender if you are comfortable with a newer AI cloud. [NEB1][NEB2][NEB3][NEB4] | 4 |
| Vultr Bare Metal | No free tier. [VUL1] | Monthly bare-metal pricing; stopped servers still incur charges; bandwidth overage billed. [VUL1][VUL3] | No managed scheduler; you install everything. [VUL1][unverified] | BYOL/self-install only. [Q1] | User-installable. [Q2] | No Vultr Block Storage attachment to bare metal; rely on local disks or external NFS/iSCSI/object paths. [VUL2][VUL3] | Easy self-serve, but not chemistry/HPC-native. [VUL1] | Monthly hardware reservation until destroy. [VUL3] | Good for DIY admins, not for fast chemsmart validation. [VUL1][VUL2][VUL3] | 2 |
| RunPod | No free tier. [RUN1] | Per-second pod/storage billing; savings plans exist; no ingress/egress fee per docs. [RUN1] | No public managed Slurm/HPC scheduler found. [RUN1][unverified] | BYOL/self-install only. [Q1] | User-installable. [Q2] | Container disk + volume + network volume billing; network volumes are separate products. [RUN1][RUN2] | Easy self-serve; Korea cards likely workable, but this is still GPU-pod economics. [RUN1][inference] | PAYG or prepaid savings plan. [RUN1] | Fine for ad hoc GPU work, poor first choice for chemsmart chemistry cluster. [RUN1][RUN2] | 1 |
| Lambda Cloud | No standing free tier; standard paid cloud plus occasional credits/promos elsewhere. [LAM1] | Public GPU pricing; no commitment or sales call needed for 1-Click Clusters per pricing page. [LAM1] | Managed Slurm available on 1-Click Clusters; SSH/firewall behavior documented. [LAM2][LAM4] | BYOL/self-install only. [Q1] | User-installable. [Q2] | Filesystems supported; standard cloud billing for resources. [LAM1][LAM3] | Good public UX, but platform is still AI-first rather than chemistry-first. [LAM1][LAM2] | PAYG. [LAM1] | Better than most GPU clouds because managed Slurm exists. [LAM1][LAM2][LAM3][LAM4] | 4 |
| Vast.ai | No free tier. [VAST1] | Prepaid credits; storage billed continuously while instances exist. [VAST1] | No public managed Slurm/HPC scheduler found. [VAST1][unverified] | BYOL/self-install only. [Q1] | User-installable. [Q2] | Marketplace storage/instance billing; data/network terms vary by host/offer. [VAST1][unverified] | Self-serve, but seller/host variability is the product. [VAST1] | Prepay plus marketplace variability. [VAST1] | Cheapest GPUs are not the same as predictable chemistry ops. [VAST1] | 1 |
| TensorDock | No free tier; homepage says start with $5. [TD1] | Public pricing language, spot available, taxes are user responsibility. [TD1][TD3] | No public managed HPC scheduler found. [TD1][unverified] | BYOL/self-install only. [Q1] | User-managed Linux VMs with SSH-key workflow. [TD2] | VM-local storage economics; spot storage billed at standard rate. [TD3] | Low entry cost, but support/hosting model is lighter-weight than hyperscalers. [TD1][TD3] | Low minimum spend; user bears tax handling. [TD1][TD3] | Easy to start, weak for a serious shared chemistry cluster. [TD1][TD2][TD3] | 1 |
| CoreWeave SUNK | No free tier for real workloads. [CW1] | Public pricing page; SUNK line item shows free software but compute/storage/network still bill. [CW1][CW4] | Managed Slurm on Kubernetes with SSH-able login nodes. [CW2][CW3] | BYOL/self-install only. [Q1] | User-installable. [Q2] | Shared storage via PVC mapping; network pricing documented separately. [CW4][CW5] | Organization approval and IAM/SCIM setup are heavier than self-serve VM clouds. [CW2][CW6] | Operational lock-in to CKS/SUNK stack. [CW2][CW6] | Strong scheduler story, but heavyweight for a first chemistry cluster. [CW1][CW2][CW3][CW4][CW5][CW6] | 3 |

## 4. Per-provider deep-dives

## ACCESS-CI
- Pricing: free to awarded projects; no end-user bill. [A4]
- Scheduler: ACCESS is a federation, so scheduler varies; Expanse is explicitly Slurm. [A3]
- Gaussian / ORCA: treat Gaussian as BYOL only [unverified]; ORCA is easy to install if site policy allows. [Q1][Q2]
- KR onboarding: weak, because project leads must be U.S.-based researchers/educators. [A1]
- Gotchas: great hardware, but direct KR-PI path is the blocker. [A1]
- Verdict: only useful if a U.S.-eligible collaborator can legally front the project. [A1]

## EuroHPC JU / PRACE legacy
- Pricing: awarded access is free; regular access is continuously open; PRACE pages are legacy/archive context only. [E1][E2][E5]
- Scheduler: not one uniform stack, but representative EuroHPC systems LUMI and Leonardo are Slurm. [E3][E4]
- Gaussian / ORCA: no public EuroHPC-wide Gaussian offer; assume BYOL/site-by-site. ORCA is technically installable if the host center permits it. [Q1][Q2]
- KR onboarding: poor for direct KR PI because eligibility centers on EU Member/Participating/associated-country entities. [E1]
- Gotchas: eligibility, not hardware, is the main issue. [E1]
- Verdict: good only through an eligible European partner. [E1]

## KISTI Nurion
- Pricing: both public paid-use process and national R&D program path are visible. [K1][K2]
- Scheduler: PBS is publicly documented. [K3]
- Gaussian / ORCA: strongest Gaussian posture in this survey; Gaussian16 and Gaussian16 Linda appear in the public software guide. ORCA is not publicly listed in reviewed pages. [K3][Q2][unverified]
- KR onboarding: strong domestic fit if you can use Korean institutional channels; SSH login, account issuance, and OTP are documented. [K1][K4]
- Gotchas: Nurion service sunset timing is now an issue; KISTI’s 2026 notice says Nurion service ends on 2026-06-30 while Neuron continues. [K2]
- Verdict: best free/academic first stop for Gaussian-aware chemsmart validation, but time-boxed because of Nurion’s sunset. [K2][K3]

## KISTI Neuron
- Pricing: same KISTI paid/program structure as above. [K1][K2]
- Scheduler: Slurm. [K5]
- Gaussian / ORCA: no public Gaussian module found; ORCA install path is straightforward in principle. [Q1][Q2][unverified]
- KR onboarding: strong for Korean institutions; shared scratch/Lustre and Slurm are public. [K1][K5][K6]
- Gotchas: better public evidence for GPU/AI workflows than for chemistry software availability. [K5]
- Verdict: best domestic fallback if Nurion access or timing fails. [K2][K5]

## KAIST KCloud
- Pricing: campus cloud, not a published commodity HPC offer. [KA1][unverified]
- Scheduler: no public batch scheduler found in reviewed KCloud pages. [KA1][unverified]
- Gaussian / ORCA: BYOL only; nothing public suggests site-licensed chemistry software. [Q1][Q2][unverified]
- KR onboarding: outsiders/alumni need account/VPN steps; SSH now flows through KCLOUDVPN/NAT. [KA2]
- Gotchas: cloud-service ergonomics are fine, but it is not a ready-made chemsmart cluster. [KA1][KA2]
- Verdict: low priority unless you already have a KAIST-internal sponsor. [KA2]

## SNU CloudFirst
- Pricing: procurement/discount support for major public clouds, not an HPC allocation service. [S1]
- Scheduler: depends on whichever cloud you buy; SNU is not exposing one scheduler itself. [S1]
- Gaussian / ORCA: BYOL on chosen cloud. [Q1][Q2]
- KR onboarding: good only for SNU labs. [S1]
- Gotchas: helpful for discounts, not for turnkey cluster operations. [S1]
- Verdict: use only if the lab is already inside SNU’s procurement lane. [S1]

## GIST Super Computing Center
- Pricing: published application and fee pages exist. [G1][G3]
- Scheduler: public pages show Slurm-backed nodes and mention global scheduler/global file system in the service stack. [G2][G4]
- Gaussian / ORCA: no public Gaussian page found; ORCA likely needs user/site install. [Q1][Q2][unverified]
- KR onboarding: realistic for regional academic collaboration. [G1]
- Gotchas: software availability for chemistry is less clear than the infrastructure itself. [G1][G2][G3]
- Verdict: respectable regional option if access politics are easier than KISTI. [G1][G2]

## UNIST Supercomputing Center
- Pricing: public application form and fee guide references exist. [U3]
- Scheduler: batch processing is explicitly supported, but the scheduler name is not obvious on the public entry pages reviewed. [U3][unverified]
- Gaussian / ORCA: no public Gaussian listing found; ORCA likely user/site install. [Q1][Q2][unverified]
- KR onboarding: good with UNIST/regional affiliation; SSH login nodes are public. [U1][U2][U3]
- Gotchas: public scheduler/software detail is lighter than KISTI’s. [U1][U2][U3]
- Verdict: useful regional fallback, especially if you already have UNIST ties. [U5]

## KREONET
- Pricing: not a compute product. [KR1]
- Scheduler: none. [KR1]
- Gaussian / ORCA: not applicable. [KR1]
- KR onboarding: important adjunct for data movement and network identity, not compute. [KR1][KR2]
- Gotchas: can help the cluster around the edges, but cannot be the cluster. [KR2]
- Verdict: out of scope for chemsmart compute procurement. [KR1][KR2]

## CloudBank
- Pricing: pay-by-use control plane over commercial clouds. [CB1]
- Scheduler: whatever you build on top of the chosen cloud. [CB1]
- Gaussian / ORCA: BYOL on the underlying cloud. [Q1][Q2]
- KR onboarding: weak because CloudBank’s current ACCESS/NAIRR framing is U.S.-researcher centric. [CB2]
- Gotchas: great spend controls, wrong primary geography. [CB1][CB2]
- Verdict: not a direct Korea-first path. [CB2]

## Google Cloud for Researchers
- Pricing: up to $5,000 credits per proposal. [GR1]
- Scheduler: you still need to build the cluster; Cluster Toolkit gives the Slurm path. [GCP1]
- Gaussian / ORCA: BYOL. [Q1][Q2]
- KR onboarding: feasible if institutional proposal is accepted. [GR1]
- Gotchas: credit size is pilot-scale, not long-horizon chemistry-cluster scale. [GR1]
- Verdict: worth applying for if you already like GCP, but not reliable enough to be the only plan. [GR1][GCP1]

## AWS Cloud Credit for Research
- Pricing: proposal-based credits for finite research projects. [AWSR1]
- Scheduler: ParallelCluster gives a clean Slurm path if credits land. [AW1]
- Gaussian / ORCA: BYOL. [Q1][Q2]
- KR onboarding: possible with institutional email, but still competitive/application-based. [AWSR1]
- Gotchas: credits are not the same as a guaranteed account. [AWSR1]
- Verdict: useful upside option, not a baseline plan. [AWSR1]

## Azure Research Credits
- Pricing: proposal-based credits. [AZR1]
- Scheduler: CycleCloud is a real HPC control plane once credits exist. [AZ1]
- Gaussian / ORCA: BYOL. [Q1][Q2]
- KR onboarding: feasible via institutional route, not instant. [AZR1]
- Gotchas: still sponsorship-gated. [AZR1]
- Verdict: decent if the lab already prefers Azure. [AZR1][AZ1]

## Oracle for Research
- Pricing: free credits for data-driven research. [ORR1]
- Scheduler: OCI’s natural chemistry/HPC route is Slurm. [OCI2]
- Gaussian / ORCA: BYOL. [Q1][Q2]
- KR onboarding: application-based, but with a good paid follow-on option if accepted. [ORR1][OCI1]
- Gotchas: credits are temporary; paid OCI posture matters more. [ORR1][OCI1]
- Verdict: strongest research-credit bridge to one of the better paid stacks. [ORR1][OCI2]

## AWS ParallelCluster
- Pricing: normal AWS compute/storage/network pricing; Spot available. [AW3][AW4]
- Scheduler: Slurm or AWS Batch; head-node SSH is explicit. [AW1][AW2]
- Gaussian / ORCA: BYOL only; nothing public suggests a site-licensed Gaussian service. [Q1][Q2]
- KR onboarding: self-serve and familiar if the lab already uses AWS. [AW3]
- Gotchas: storage and data-egress line items add up unless you design deliberately. [AW3][AW4]
- Verdict: safest mainstream paid choice if you want the least surprise in scheduler behavior. [AW1][AW2]

## Azure CycleCloud
- Pricing: standard Azure billing plus Spot options. [AZ3][AZ4]
- Scheduler: unusually flexible; official templates include PBS Pro, LSF, Grid Engine, Slurm, HTCondor. [AZ1]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: strong self-serve if Azure is already approved internally. [AZ3]
- Gotchas: more control-plane complexity than a single Terraform-and-go Slurm stack. [AZ1][AZ2]
- Verdict: best if your team cares about non-Slurm scheduler portability. [AZ1]

## Google Cloud Cluster Toolkit
- Pricing: normal GCE/storage/egress pricing. [GCP3]
- Scheduler: documented Slurm quickstart; SSH uses standard Compute Engine primitives. [GCP1][GCP2]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: clean self-serve if GCP billing is already solved. [GCP2][GCP3]
- Gotchas: less opinionated than AWS ParallelCluster, so more design choices land on you. [GCP1]
- Verdict: very good paid option if you want transparent building blocks. [GCP1][GCP2]

## Oracle Cloud HPC
- Pricing: public OCI pricing and standard PAYG. [OCI1]
- Scheduler: OCI HPC guidance centers on Slurm plus SSH/bastion patterns. [OCI2][OCI3]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: workable if vendor approval and billing are acceptable. [OCI1][OCI3]
- Gotchas: needs live hands-on validation for operational smoothness before standardization. [OCI3]
- Verdict: strongest budget-conscious paid candidate on paper. [OCI1][OCI2]

## Rescale
- Pricing: opaque in public pages; effectively demo/quote-led. [RES1][RES4]
- Scheduler: supports or integrates with Slurm and other schedulers. [RES2]
- Gaussian / ORCA: Gaussian is mentioned in platform materials, but licensing posture is not public. [RES3][unverified]
- KR onboarding: likely sales-led rather than instant. [RES4][inference]
- Gotchas: opacity is the problem; you pay a premium to remove infra work, but first-cluster economics become hard to judge. [RES1][RES2][RES4]
- Verdict: avoid for a cheap first validation cluster. [RES1][RES4]

## Penguin POD
- Pricing: public datasheet is old; current terms likely require sales confirmation. [POD1][POD2][unverified-old]
- Scheduler: classic HPC environment, but current public pages reviewed do not cleanly state the scheduler. [POD1][POD3][unverified]
- Gaussian / ORCA: no public chemistry-software stance found. [Q1][Q2][unverified]
- KR onboarding: probably contract-led. [POD1][inference]
- Gotchas: dated public collateral makes budgeting risky. [POD2][unverified-old]
- Verdict: interesting only if you want a vendor-run bare-metal HPC cloud and can tolerate sales cycles. [POD1][POD2]

## Hyperstack
- Pricing: public on-demand/reserved/spot pricing; ingress/egress free per page. [HS1][HS2]
- Scheduler: no public managed Slurm/HPC scheduler found. [HS1][unverified]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: self-serve seems plausible, but chemistry/HPC workflows are not the product center of gravity. [HS1][inference]
- Gotchas: cheap GPU != ready shared chemistry cluster. [HS1][HS2]
- Verdict: avoid unless low-cost GPUs matter more than scheduler and filesystem discipline. [HS1][HS2]

## Crusoe Cloud
- Pricing: minute-billed on-demand/spot/reserved; no ingress/egress charge per pricing page. [CR1]
- Scheduler: Managed Slurm with dedicated login nodes. [CR2]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: better than many startups because pricing is public and not purely sales-gated. [CR1]
- Gotchas: still AI-first; chemistry reference designs are not the public focus. [CR1][CR2]
- Verdict: serious second-tier paid option if AWS/GCP/OCI are undesirable. [CR1][CR2]

## Nebius AI Cloud
- Pricing: public PAYG plus optional commitment discounts; explicit card/bank-transfer support and $25 first-payment minimum. [NEB1][NEB3]
- Scheduler: managed Slurm/Soperator positioning is explicit. [NEB2][NEB4]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: stronger than many startups because payment method and minimum entry are documented. [NEB1]
- Gotchas: newer vendor, so organizational procurement comfort may lag technical merit. [NEB1][NEB4]
- Verdict: good paid challenger if you want modern Slurm without hyperscaler complexity. [NEB1][NEB2][NEB3][NEB4]

## Vultr Bare Metal
- Pricing: monthly hardware pricing; stopped servers still bill; bandwidth overages bill too. [VUL1][VUL3]
- Scheduler: fully DIY. [VUL1][unverified]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: easy enough operationally, but this is generic bare metal, not HPC-as-a-service. [VUL1]
- Gotchas: no block-storage attachment to bare metal. [VUL2]
- Verdict: only for teams that want to be their own cluster admins. [VUL1][VUL2][VUL3]

## RunPod
- Pricing: per-second pods and storage; savings plans available; no ingress/egress fee per docs. [RUN1]
- Scheduler: no public managed Slurm found. [RUN1][unverified]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: easy self-serve, but the product is pod-centric rather than shared-cluster-centric. [RUN1]
- Gotchas: persistent storage design is your problem, and scheduler semantics are weak. [RUN1][RUN2]
- Verdict: avoid for first chemsmart cluster work. [RUN1][RUN2]

## Lambda Cloud
- Pricing: public GPU pricing and no sales call required for 1-Click Clusters. [LAM1]
- Scheduler: managed Slurm exists; SSH/firewall behavior is documented. [LAM2][LAM4]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: easier than most HPCaaS because public pricing and docs are concrete. [LAM1][LAM2]
- Gotchas: AI-first platform; chemistry software still means you are the integrator. [LAM2][LAM3]
- Verdict: one of the few GPU clouds I would consider for chemsmart if you insist on a non-hyperscaler. [LAM1][LAM2]

## Vast.ai
- Pricing: prepaid credits and always-on storage billing while the instance exists. [VAST1]
- Scheduler: no public managed Slurm/HPC scheduler found. [VAST1][unverified]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: easy to start, but host variability is fundamental to the product. [VAST1]
- Gotchas: cheapest marketplace capacity often means the most operational variance. [VAST1]
- Verdict: avoid for shared chemistry infrastructure. [VAST1]

## TensorDock
- Pricing: low entry point, public pricing language, spot, and user-paid tax responsibility. [TD1][TD3]
- Scheduler: no public managed Slurm/HPC scheduler found. [TD1][unverified]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: easy enough for a single VM, less convincing for a shared chemistry cluster. [TD1][TD2]
- Gotchas: too lightweight and host-ops-sensitive for the target use case. [TD1][TD3]
- Verdict: avoid for first chemsmart validation. [TD1][TD2][TD3]

## CoreWeave SUNK
- Pricing: compute/storage/network bill normally even though SUNK software is labeled free. [CW1][CW4]
- Scheduler: excellent managed Slurm story with SSH-able login nodes. [CW2][CW3]
- Gaussian / ORCA: BYOL only. [Q1][Q2]
- KR onboarding: heavier org/IAM provisioning than simple VM clouds. [CW2][CW6]
- Gotchas: operationally powerful but overbuilt for a first chemistry cluster. [CW2][CW5][CW6]
- Verdict: good for large orgs already committed to CoreWeave, not for a cheap first cluster. [CW1][CW2][CW3]

## 5. Recommendation block

### Cheapest free start
1. **KISTI Nurion** — best documented chemistry fit because public docs show **PBS + Gaussian16/Gaussian16 Linda + SSH login + shared HPC storage**; main risk is the announced **2026-06-30** service end. [K2][K3][K4]
2. **KISTI Neuron** — best domestic fallback if Nurion timing or software policy blocks you; strong Slurm/storage story, weaker public Gaussian evidence. [K1][K5][K6]
3. **UNIST or GIST regional center** — only if you already have local institutional sponsorship; better than overseas grant programs for KR friction, but chemistry software evidence is thinner. [G1][G2][G3][U1][U2][U3]

### Most reasonable paid
1. **Oracle Cloud HPC** — strong cost discipline case, explicit HPC/Slurm posture, standard SSH/bastion access. [OCI1][OCI2][OCI3]
2. **AWS ParallelCluster** — most mature docs and lowest risk of getting lost in cluster bring-up. [AW1][AW2]
3. **Google Cloud Cluster Toolkit** — good if you want transparent Slurm automation and already prefer GCP primitives. [GCP1][GCP2][GCP3]

### Avoid for first pass
1. **Rescale** — public pricing is too opaque, and Gaussian licensing posture is not publicly clean. [RES1][RES3][RES4]
2. **Vast.ai** — prepaid marketplace economics and host variability are a bad match for reproducible shared chemistry operations. [VAST1]
3. **TensorDock / RunPod class** — easy to start, but weak scheduler/shared-filesystem posture for chemsmart’s target workflow. [RUN1][RUN2][TD1][TD2][TD3]

### Concrete next-step plan
1. Ask the lab/admin side one binary question first: **“Must g16 be available on day one?”** If yes, try **Nurion** first, then **OCI/AWS** only as BYOL. [K3][Q1]
2. In parallel, request/verify two domestic paths: **KISTI account eligibility** and **one regional-center fallback (UNIST or GIST)**. [K1][G1][U3]
3. If paid cloud is needed, prototype the same chemsmart server shape on **OCI first**, **AWS second**, using **Slurm/PBS + shared scratch/home + SSH login node** only; do not start with marketplace GPU vendors. [OCI2][AW1][AW2]
4. Before any spend, confirm **Gaussian license portability** and **ORCA site-policy acceptance** with the exact target provider/admin. [Q1][Q2]

## 6. Open questions

- Does the lab require **Gaussian g16 on day one**, or is **ORCA-first** acceptable for chemsmart validation?
- Can the PI legally/operationally use **KISTI** or one of **UNIST/GIST** regional centers right now?
- For public cloud, is the priority **lowest cash outlay** or **lowest setup time**?
- No current public, self-serve **HPC vendor trial-credit** program was cleanly confirmed from HPE/Dell/Lenovo-class vendors in this pass; if this matters, it needs a separate follow-up pass and likely sales/contact-page confirmation. [unverified]
- Public docs did **not** cleanly confirm a preinstalled Gaussian stance for most providers beyond Nurion; each target admin/provider should confirm BYOL legality and module policy before rollout. [K3][Q1]

## 7. Sources

- [Q1] Gaussian, Inc. US Commercial Price List — https://gaussian.com/wp-content/uploads/dl/us_com.pdf (accessed 2026-05-11)
- [Q2] ORCA service page — https://www.kofo.mpg.de/en/research/services/orca (accessed 2026-05-11)
- [A1] ACCESS Allocations Policy — https://allocations.access-ci.org/allocations-policy (accessed 2026-05-11)
- [A2] ACCESS Prepare Requests — https://allocations.access-ci.org/prepare-requests (accessed 2026-05-11)
- [A3] SDSC Expanse CPU on ACCESS — https://support.access-ci.org/rp-documentation/sdsc-expanse-cpu (accessed 2026-05-11)
- [A4] ACCESS home — https://access-ci.org/ (accessed 2026-05-11)
- [E1] EuroHPC access policy and FAQ — https://www.eurohpc-ju.europa.eu/supercomputers/supercomputers-access-policy-and-faq_en (accessed 2026-05-11)
- [E2] EuroHPC regular access call details — https://www.eurohpc-ju.europa.eu/document/download/004ebf96-38c2-41a9-ac59-0c252a0267da_en?filename=Regular+Access+-+Full+Call+Details-FINAL.pdf (accessed 2026-05-11)
- [E3] LUMI Slurm quickstart — https://docs.lumi-supercomputer.eu/runjobs/scheduled-jobs/slurm-quickstart/ (accessed 2026-05-11)
- [E4] Leonardo CINECA docs — https://docs.hpc.cineca.it/hpc/leonardo.html (accessed 2026-05-11)
- [E5] PRACE legacy project access — https://prace-ri.eu/resources/legacy-hpc-access/project-access/ (accessed 2026-05-11; [dead link on curl validation: 401])
- [K1] KISTI paid-use process — https://www.ksc.re.kr/jwsc/gjbg/jwscan (accessed 2026-05-11)
- [K2] KISTI 2026 R&D innovation notice — https://www.ksc.re.kr/notice/gjsh/gjsh/view?gjshkey=131 (accessed 2026-05-11)
- [K3] Nurion guide home — https://docs-ksc.gitbook.io/nurion-user-guide-eng (accessed 2026-05-11)
- [K4] Nurion user environment / SSH — https://docs-ksc.gitbook.io/nurion-user-guide-eng/system/user-environment (accessed 2026-05-11)
- [K5] Neuron Slurm guide — https://docs-ksc.gitbook.io/neuron-user-guide-eng/system/running-jobs-through-scheduler-slurm (accessed 2026-05-11)
- [K6] Neuron Lustre guide — https://docs-ksc.gitbook.io/neuron-user-guide-eng/appendix/appendix-2-how-to-use-lustre-striping (accessed 2026-05-11)
- [KA1] KAIST KCloud tutorial — https://kcloud.kaist.ac.kr/index.php/kcloud2-tutorial/ (accessed 2026-05-11)
- [KA2] KAIST KCloud access notice — https://kcloud.kaist.ac.kr/index.php/notice/?mod=document&uid=220 (accessed 2026-05-11)
- [S1] SNU CloudFirst — https://ist.snu.ac.kr/cloudfirst/ (accessed 2026-05-11)
- [G1] GIST resource-application guide — https://scent.gist.ac.kr/scent/sub06_01_01.do (accessed 2026-05-11; [dead link on curl validation: 000])
- [G2] GIST AI-X cluster architecture — https://scent.gist.ac.kr/scent/sub02_01_02.do (accessed 2026-05-11; [dead link on curl validation: 000])
- [G3] GIST pricing guide — https://scent.gist.ac.kr/scent/sub06_01_03.do (accessed 2026-05-11; [dead link on curl validation: 000])
- [G4] GIST PLSI & SCENT service stack — https://scent.gist.ac.kr/scent/sub04_01_01.do (accessed 2026-05-11; [dead link on curl validation: 000])
- [U1] UNIST new user information — https://usc.unist.ac.kr/new-user-information/ (accessed 2026-05-11)
- [U2] UNIST SSH access guide — https://usc.unist.ac.kr/access-to-hpcs-how-to-access-hpc-clusters-via-ssh-client/ (accessed 2026-05-11)
- [U3] UNIST technical support / apply account — https://usc.unist.ac.kr/technical-support/ and https://usc.unist.ac.kr/apply-account/ (accessed 2026-05-11)
- [U4] UNIST hardware page — https://usc.unist.ac.kr/hardware/ (accessed 2026-05-11)
- [U5] UNIST mission and role — https://usc.unist.ac.kr/mission-and-role/ (accessed 2026-05-11)
- [KR1] KREONET intro / service context — https://eduroam.kreonet.net/ and https://wiki.kreonet.net/chumdan/%ED%81%AC%EB%A0%88%EC%98%A4%EB%84%B7-%EC%86%8C%EA%B0%9C-51119269.html (accessed 2026-05-11)
- [KR2] KREONET Science DMZ guide — https://wiki.kreonet.net/faster-data/science-dmz-25985496.html (accessed 2026-05-11)
- [CB1] CloudBank about / welcome — https://www.cloudbank.org/about and https://www.cloudbank.org/ (accessed 2026-05-11)
- [CB2] CloudBank now available through ACCESS and NAIRR — https://www.cloudbank.org/news/cloudbank-now-available-through-access-and-nairr-pilot (accessed 2026-05-11)
- [GR1] Google Cloud for Researchers — https://cloud.google.com/edu/researchers (accessed 2026-05-11)
- [AWSR1] AWS Cloud Credit for Research — https://aws.amazon.com/government-education/research-and-technical-computing/cloud-credit-for-research/ (accessed 2026-05-11)
- [AZR1] Azure Research Credits — https://www.microsoft.com/en-us/azure-academic-research/default.aspx (accessed 2026-05-11; [dead link on curl validation: 403])
- [ORR1] Oracle for Research one-pager — https://www.oracle.com/a/ocom/docs/cloud/oracle-for-research-one-pager.pdf (accessed 2026-05-11)
- [AW1] AWS ParallelCluster schedulers — https://docs.aws.amazon.com/parallelcluster/latest/ug/schedulers-v3.html (accessed 2026-05-11)
- [AW2] AWS ParallelCluster head-node connect — https://docs.aws.amazon.com/en_us/parallelcluster/latest/ug/headnode-connect-v3.html (accessed 2026-05-11)
- [AW3] AWS EC2 On-Demand pricing — https://aws.amazon.com/ec2/pricing/on-demand/ (accessed 2026-05-11)
- [AW4] AWS EC2 Spot pricing — https://aws.amazon.com/ec2/spot/pricing/ (accessed 2026-05-11)
- [AZ1] Azure CycleCloud overview — https://learn.microsoft.com/en-us/azure/cyclecloud/overview?view=cyclecloud-7 (accessed 2026-05-11)
- [AZ2] Azure CycleCloud user access — https://learn.microsoft.com/en-us/azure/cyclecloud/how-to/user-access?view=cyclecloud-8 (accessed 2026-05-11)
- [AZ3] Azure Linux VM pricing — https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/ (accessed 2026-05-11)
- [AZ4] Azure Spot Virtual Machines portal guide — https://learn.microsoft.com/en-us/azure/virtual-machines/spot-portal (accessed 2026-05-11)
- [GCP1] Google Cluster Toolkit Slurm quickstart — https://cloud.google.com/cluster-toolkit/docs/quickstarts/slurm-cluster (accessed 2026-05-11)
- [GCP2] Google Compute Engine SSH — https://cloud.google.com/compute/docs/instances/ssh (accessed 2026-05-11)
- [GCP3] Google Compute pricing — https://cloud.google.com/compute/all-pricing (accessed 2026-05-11)
- [OCI1] Oracle Cloud pricing — https://www.oracle.com/cloud/pricing/ (accessed 2026-05-11)
- [OCI2] Oracle HPC cluster networks — https://docs.oracle.com/en-us/iaas/Content/Compute/Concepts/cluster-networks.htm (accessed 2026-05-11)
- [OCI3] OCI Bastion for researchers / bastion overview — https://docs.oracle.com/en/programs/research/bastion-service and https://docs.oracle.com/en-us/iaas/Content/Bastion/Concepts/bastionoverview.htm (accessed 2026-05-11)
- [RES1] Rescale Compute — https://rescale.com/ko/platform/compute/ (accessed 2026-05-11)
- [RES2] Rescale hybrid cloud solutions — https://rescale.com/lp/hybrid-cloud-solutions-v2/ (accessed 2026-05-11)
- [RES3] Rescale Gaussian mention — https://rescale.com/lp/vertex-rd-solutions/ (accessed 2026-05-11)
- [RES4] Rescale contact page — https://rescale.com/contact-us/ (accessed 2026-05-11)
- [POD1] Penguin POD home — https://pod.penguincomputing.com/ (accessed 2026-05-11; [dead link on curl validation: 000])
- [POD2] Penguin POD pricing datasheet — https://www.penguinsolutions.com/wp-content/uploads/2021/11/pod-pricing-datasheet-111121.pdf (accessed 2026-05-11)
- [POD3] Penguin POD applications — https://pod.penguincomputing.com/documentation/applications.html (accessed 2026-05-11; [dead link on curl validation: 000])
- [HS1] Hyperstack pricing — https://www.hyperstack.cloud/gpu-pricing (accessed 2026-05-11)
- [HS2] Hyperstack spot VMs — https://www.hyperstack.cloud/spot-vms (accessed 2026-05-11)
- [CR1] Crusoe Cloud pricing — https://www.crusoe.ai/cloud/pricing (accessed 2026-05-11)
- [CR2] Crusoe Managed Slurm overview — https://docs.crusoecloud.com/orchestration/slurm/overview (accessed 2026-05-11)
- [NEB1] Nebius pricing — https://nebius.com/prices (accessed 2026-05-11)
- [NEB2] Nebius managed Soperator — https://docs.nebius.com/slurm-soperator/managed-soperator/manage (accessed 2026-05-11)
- [NEB3] Nebius PAYG and storage types — https://docs.nebius.com/signup-billing/billing-models/payg and https://docs.nebius.com/compute/storage/types (accessed 2026-05-11)
- [NEB4] Nebius AI Cloud overview — https://nebius.com/ai-cloud (accessed 2026-05-11)
- [VUL1] Vultr bare metal pricing/docs — https://docs.vultr.com/reference/vultr-cli/plans/metal and https://docs.vultr.com/products/compute/bare-metal/provisioning (accessed 2026-05-11)
- [VUL2] Vultr block storage on bare metal — https://docs.vultr.com/support/products/storage/can-i-attach-vultr-block-storage-volume-to-vultr-bare-metal-server (accessed 2026-05-11)
- [VUL3] Vultr billing docs — https://docs.vultr.com/support/platform/billing/do-stopped-bare-metal-servers-incur-charges and https://docs.vultr.com/support/platform/billing/what-is-the-bandwidth-overage-rate (accessed 2026-05-11)
- [RUN1] RunPod pricing — https://docs.runpod.io/pods/pricing (accessed 2026-05-11)
- [RUN2] RunPod network volumes — https://docs.runpod.io/serverless/storage/network-volumes (accessed 2026-05-11)
- [LAM1] Lambda pricing — https://lambda.ai/service/gpu-cloud/pricing (accessed 2026-05-11)
- [LAM2] Lambda Managed Slurm — https://docs.lambda.ai/public-cloud/1-click-clusters/managed-slurm/ (accessed 2026-05-11)
- [LAM3] Lambda filesystems — https://docs.lambda.ai/public-cloud/filesystems/ (accessed 2026-05-11)
- [LAM4] Lambda firewalls / SSH defaults — https://docs.lambda.ai/public-cloud/firewalls/ (accessed 2026-05-11)
- [VAST1] Vast billing — https://docs.vast.ai/billing (accessed 2026-05-11)
- [TD1] TensorDock homepage — https://www.tensordock.com/ (accessed 2026-05-11)
- [TD2] TensorDock SSH docs — https://docs.tensordock.com/virtual-machines/how-to-add-your-ssh-key and https://docs.tensordock.com/virtual-machines/how-to-ssh-into-your-instance (accessed 2026-05-11)
- [TD3] TensorDock spot/tax docs — https://docs.tensordock.com/virtual-machines/spot-instances and https://docs.tensordock.com/legal-information/taxes-vat-gst (accessed 2026-05-11)
- [CW1] CoreWeave pricing — https://coreweave.com/pricing (accessed 2026-05-11)
- [CW2] Create a SUNK cluster — https://docs.coreweave.com/products/sunk/deploy_sunk/create-sunk-cluster (accessed 2026-05-11)
- [CW3] CoreWeave compute and login nodes — https://docs.coreweave.com/products/sunk/slurm-on-sunk/compute-and-login-nodes (accessed 2026-05-11)
- [CW4] CoreWeave network pricing — https://docs.coreweave.com/docs/pricing/pricing-networking (accessed 2026-05-11)
- [CW5] CoreWeave shared storage — https://docs.coreweave.com/docs/products/sunk/manage_sunk/shared-storage (accessed 2026-05-11)
- [CW6] CoreWeave user provisioning / account setup — https://docs.coreweave.com/products/sunk/manage_sunk/control_cluster_access/sunk_user_provisioning and https://docs.coreweave.com/docs/platform (accessed 2026-05-11)
