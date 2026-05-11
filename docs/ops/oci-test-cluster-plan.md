# OCI test cluster plan for chemsmart agent

> Status: planning only. Do **not** run any `oci ... create`, `launch`, or
> `terraform apply` commands from this document until the orchestrator gives
> explicit authorization.

## Auth diagnosis

### What failed on 2026-05-11

With `OCI_CLI_AUTH=security_token` set, these read-only checks were run:

- `oci iam region-subscription list --region ap-seoul-1` → `TenantNotFound`
- `oci iam region-subscription list --region us-ashburn-1` → `TenantNotFound`
- `oci iam region-subscription list --region ap-osaka-1` → `TenantNotFound`
- `oci iam region-subscription list --region ap-chuncheon-1` → success

Successful output in `ap-chuncheon-1` showed:

- `is-home-region: true`
- `region-name: ap-chuncheon-1`

Additional read-only checks that succeeded in `ap-chuncheon-1`:

- `oci iam availability-domain list`
- `oci compute shape list` for `VM.Standard.A1.Flex`
- `oci compute image list` for Ubuntu 22.04

Observed standard VM shapes in this home region for this tenancy on 2026-05-11:

- `VM.Standard.A1.Flex`
- `VM.Standard.E2.1.Micro`

### Diagnosis

The tenancy is valid, and the security-token session is valid. The real issue is
**home-region mismatch**:

- the tenancy home region is **`ap-chuncheon-1`**
- the original failures came from calling IAM tenancy-scoped APIs against
  **`ap-seoul-1`**

This matters twice:

1. IAM tenancy reads should use the home region when region-sensitive behavior
   appears.
2. Oracle's Always Free documentation says Always Free compute instances are
   provisioned in the **home region**, so the cheapest plan should target
   **`ap-chuncheon-1`**, not `ap-seoul-1`.

### Immediate operator action

Before provisioning anything, export the correct region:

```bash
export OCI_CLI_AUTH=security_token
export OCI_REGION=ap-chuncheon-1
```

Quick re-check:

```bash
oci iam region-subscription list --all --region "$OCI_REGION"
```

Expected result: only `ap-chuncheon-1`, with `is-home-region: true`.

### Architecture caution: ORCA on Arm

The preferred cheap shape is `VM.Standard.A1.Flex` (Arm). However, the official
ORCA installation docs currently show Linux installer examples named
`orca_..._linux_x86-64_...run`, and do not show a Linux `aarch64`/Arm build.
That means:

- the **OCI auth problem is solved**
- but **ORCA-on-Arm compatibility must be confirmed before launch**

Practical consequence:

- **Best-case / cheapest path:** use `VM.Standard.A1.Flex` only if you already
  have an ORCA build confirmed to run on OCI Arm Linux.
- **Fallback path:** if ORCA is x86-64 only, this tenancy's visible x86 Always
  Free shape is `VM.Standard.E2.1.Micro`, which is suitable only for a minimal
  scheduler smoke test and is likely too constrained for a comfortable
  Slurm + ORCA workflow.

## ASCII architecture

### Preferred single-node plan

```text
OCI tenancy (home region: ap-chuncheon-1)
└── root compartment (or dedicated child compartment)
    └── VCN 10.42.0.0/16
        ├── Internet Gateway
        ├── Route Table
        │   └── 0.0.0.0/0 -> IGW
        ├── Security List
        │   ├── ingress tcp/22 from <YOUR_PUBLIC_IP>/32
        │   ├── ingress all from 10.42.0.0/16   (future 2-node Slurm option)
        │   └── egress all to 0.0.0.0/0
        └── Public Subnet 10.42.1.0/24
            └── 1 x VM.Standard.A1.Flex (4 OCPU, 24 GB) [preferred if ORCA-on-Arm confirmed]
                ├── Ubuntu 22.04
                ├── sshd
                ├── munge
                ├── slurmctld
                ├── slurmd
                ├── chemsmart runtime
                ├── ORCA (only if compatible build is provided)
                └── scratch: /home/ubuntu/scratch
```

### Optional 2-node variant if quota and compatibility allow

```text
same VCN/subnet
├── head node: slurmctld + sshd + chemsmart
└── compute node: slurmd + ORCA
```

For this validation task, a **single head+compute node** is enough.

## Provisioning CLI

### 1. Export variables

Use the root compartment unless you intentionally create a child compartment.

```bash
export OCI_CLI_AUTH=security_token
export OCI_REGION=ap-chuncheon-1
export TENANCY_OCID='ocid1.tenancy.oc1..aaaaaaaabp4dih3ybtil4qjoxchz33sjd22kih6u5ov5eq4rffwpwapxlt5a'
export COMPARTMENT_OCID="$TENANCY_OCID"

export CLUSTER_PREFIX='chemsmart-slurm'
export VCN_CIDR='10.42.0.0/16'
export SUBNET_CIDR='10.42.1.0/24'
export VCN_DNS='chemvcn'
export SUBNET_DNS='pub1'
export HOSTNAME='chemslurm1'

export SHAPE='VM.Standard.A1.Flex'
export OCPUS='4'
export MEMORY_GB='24'
export BOOT_GB='100'

export SSH_KEY="$HOME/.ssh/${CLUSTER_PREFIX}_ed25519"
export SSH_PUB="${SSH_KEY}.pub"

# Replace with your own IP if curl-based discovery is not desired.
export MY_IP="$(curl -fsSL https://ifconfig.me/ip)"

# Leave as REQUIRED until you have a compatible installer staging method.
# Examples: direct HTTPS URL, or OCI Object Storage pre-authenticated request URL.
export ORCA_RUNFILE_URL='REQUIRED'

export AD="$(oci iam availability-domain list \
  --compartment-id "$TENANCY_OCID" \
  --region "$OCI_REGION" \
  --query 'data[0].name' \
  --raw-output)"
```

### 2. Generate an SSH keypair

```bash
[ -f "$SSH_KEY" ] || ssh-keygen -t ed25519 -N '' -C "$CLUSTER_PREFIX" -f "$SSH_KEY"
```

### 3. Re-validate auth and the target shape/image

```bash
oci iam region-subscription list --all --region "$OCI_REGION"

oci compute shape list \
  --compartment-id "$COMPARTMENT_OCID" \
  --availability-domain "$AD" \
  --region "$OCI_REGION" \
  --all \
  --query 'data[?shape==`VM.Standard.A1.Flex`].shape'

export IMAGE_ID="$(oci compute image list \
  --compartment-id "$COMPARTMENT_OCID" \
  --region "$OCI_REGION" \
  --operating-system 'Canonical Ubuntu' \
  --operating-system-version '22.04' \
  --shape "$SHAPE" \
  --all \
  --sort-by TIMECREATED \
  --sort-order DESC \
  --query 'data[0].id' \
  --raw-output)"

printf 'AD=%s\nIMAGE_ID=%s\n' "$AD" "$IMAGE_ID"
```

### 4. Write the cloud-init file

This installs Ubuntu packages, configures single-node Slurm, creates
`/home/ubuntu/scratch`, and optionally installs ORCA if
`ORCA_RUNFILE_URL` points to a compatible installer.

**Do not use the Arm/A1 path unless ORCA-on-Arm is confirmed.**

```bash
cat > cloud-init.yaml <<EOF
#cloud-config
package_update: true
package_upgrade: false
packages:
  - curl
  - jq
  - munge
  - openssh-server
  - slurm-wlm
  - slurm-wlm-basic-plugins
  - unzip
write_files:
  - path: /etc/slurm/slurm.conf
    owner: root:root
    permissions: '0644'
    content: |
      ClusterName=chemsmart-oci
      SlurmctldHost=${HOSTNAME}
      MpiDefault=none
      ProctrackType=proctrack/linuxproc
      ReturnToService=2
      SlurmctldPidFile=/run/slurmctld.pid
      SlurmdPidFile=/run/slurmd.pid
      SlurmUser=slurm
      SlurmdSpoolDir=/var/spool/slurmd
      StateSaveLocation=/var/spool/slurmctld
      SwitchType=switch/none
      TaskPlugin=task/affinity,task/cgroup
      SchedulerType=sched/backfill
      SelectType=select/cons_tres
      SelectTypeParameters=CR_Core_Memory
      AuthType=auth/munge
      SlurmctldPort=6817
      SlurmdPort=6818
      NodeName=${HOSTNAME} CPUs=${OCPUS} RealMemory=23552 State=UNKNOWN
      PartitionName=debug Nodes=${HOSTNAME} Default=YES MaxTime=INFINITE State=UP
  - path: /usr/local/sbin/chemsmart-firstboot.sh
    owner: root:root
    permissions: '0755'
    content: |
      #!/usr/bin/env bash
      set -euxo pipefail
      hostnamectl set-hostname ${HOSTNAME}
      install -d -o slurm -g slurm /var/spool/slurmctld /var/spool/slurmd
      install -d -m 0755 -o ubuntu -g ubuntu /home/ubuntu/scratch
      if command -v create-munge-key >/dev/null 2>&1; then
        create-munge-key
      else
        dd if=/dev/urandom bs=1 count=1024 of=/etc/munge/munge.key
      fi
      chown munge:munge /etc/munge/munge.key
      chmod 0400 /etc/munge/munge.key
      systemctl enable --now munge
      if [ "${ORCA_RUNFILE_URL}" != "REQUIRED" ]; then
        mkdir -p /opt/orca
        curl -fL "${ORCA_RUNFILE_URL}" -o /tmp/orca.run
        chmod +x /tmp/orca.run
        /tmp/orca.run -- -p /opt/orca
        cat >/etc/profile.d/orca.sh <<'ORCAEOF'
        export PATH=/opt/orca:\$PATH
        export LD_LIBRARY_PATH=/opt/orca:\$LD_LIBRARY_PATH
        ORCAEOF
      fi
      systemctl enable --now slurmctld
      systemctl enable --now slurmd
runcmd:
  - [ bash, -lc, '/usr/local/sbin/chemsmart-firstboot.sh' ]
EOF
```

### 5. Create network resources

```bash
export VCN_ID="$(oci network vcn create \
  --compartment-id "$COMPARTMENT_OCID" \
  --region "$OCI_REGION" \
  --display-name "${CLUSTER_PREFIX}-vcn" \
  --dns-label "$VCN_DNS" \
  --cidr-blocks "[\"$VCN_CIDR\"]" \
  --wait-for-state AVAILABLE \
  --query 'data.id' \
  --raw-output)"

export IGW_ID="$(oci network internet-gateway create \
  --compartment-id "$COMPARTMENT_OCID" \
  --region "$OCI_REGION" \
  --vcn-id "$VCN_ID" \
  --display-name "${CLUSTER_PREFIX}-igw" \
  --is-enabled true \
  --wait-for-state AVAILABLE \
  --query 'data.id' \
  --raw-output)"

export RT_ID="$(oci network route-table create \
  --compartment-id "$COMPARTMENT_OCID" \
  --region "$OCI_REGION" \
  --vcn-id "$VCN_ID" \
  --display-name "${CLUSTER_PREFIX}-rt" \
  --route-rules '[{"destination":"0.0.0.0/0","destinationType":"CIDR_BLOCK","networkEntityId":"'"$IGW_ID"'"}]' \
  --wait-for-state AVAILABLE \
  --query 'data.id' \
  --raw-output)"

export SL_ID="$(oci network security-list create \
  --compartment-id "$COMPARTMENT_OCID" \
  --region "$OCI_REGION" \
  --vcn-id "$VCN_ID" \
  --display-name "${CLUSTER_PREFIX}-sl" \
  --ingress-security-rules '[
    {"description":"SSH from operator IP","protocol":"6","source":"'"$MY_IP"'/32","sourceType":"CIDR_BLOCK","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":22,"max":22}}},
    {"description":"Intra-VCN traffic for future 2-node Slurm","protocol":"all","source":"'"$VCN_CIDR"'","sourceType":"CIDR_BLOCK","isStateless":false}
  ]' \
  --egress-security-rules '[
    {"description":"Allow all outbound","protocol":"all","destination":"0.0.0.0/0","destinationType":"CIDR_BLOCK","isStateless":false}
  ]' \
  --wait-for-state AVAILABLE \
  --query 'data.id' \
  --raw-output)"

export SUBNET_ID="$(oci network subnet create \
  --compartment-id "$COMPARTMENT_OCID" \
  --region "$OCI_REGION" \
  --vcn-id "$VCN_ID" \
  --display-name "${CLUSTER_PREFIX}-public-subnet" \
  --dns-label "$SUBNET_DNS" \
  --cidr-block "$SUBNET_CIDR" \
  --route-table-id "$RT_ID" \
  --security-list-ids "[\"$SL_ID\"]" \
  --prohibit-public-ip-on-vnic false \
  --wait-for-state AVAILABLE \
  --query 'data.id' \
  --raw-output)"

printf 'VCN_ID=%s\nIGW_ID=%s\nRT_ID=%s\nSL_ID=%s\nSUBNET_ID=%s\n' \
  "$VCN_ID" "$IGW_ID" "$RT_ID" "$SL_ID" "$SUBNET_ID"
```

### 6. Launch the single-node Slurm VM

```bash
export INSTANCE_ID="$(oci compute instance launch \
  --compartment-id "$COMPARTMENT_OCID" \
  --region "$OCI_REGION" \
  --availability-domain "$AD" \
  --display-name "$HOSTNAME" \
  --hostname-label "$HOSTNAME" \
  --shape "$SHAPE" \
  --shape-config '{"ocpus":4,"memoryInGBs":24}' \
  --subnet-id "$SUBNET_ID" \
  --assign-public-ip true \
  --image-id "$IMAGE_ID" \
  --boot-volume-size-in-gbs "$BOOT_GB" \
  --ssh-authorized-keys-file "$SSH_PUB" \
  --user-data-file cloud-init.yaml \
  --wait-for-state RUNNING \
  --query 'data.id' \
  --raw-output)"

export PUBLIC_IP="$(oci compute instance list-vnics \
  --compartment-id "$COMPARTMENT_OCID" \
  --instance-id "$INSTANCE_ID" \
  --query 'data[0]."public-ip"' \
  --raw-output)"

printf 'INSTANCE_ID=%s\nPUBLIC_IP=%s\n' "$INSTANCE_ID" "$PUBLIC_IP"
```

### 7. Verify the node over SSH

```bash
ssh -i "$SSH_KEY" ubuntu@"$PUBLIC_IP" '
  set -euxo pipefail
  hostname
  systemctl is-active munge slurmctld slurmd
  sinfo
  scontrol show nodes
  test -d /home/ubuntu/scratch
  ls -ld /home/ubuntu/scratch
  command -v orca || true
'
```

### 8. Optional: second node

If quota allows and ORCA compatibility is clear, repeat the instance launch with
another hostname, then expand `/etc/slurm/slurm.conf` and restart Slurm. For
this chemsmart validation, that is optional.

## Cost

### Expected cost for the preferred plan

If the tenancy can use Oracle Always Free in its home region and the entire
cluster stays within Always Free limits, the target cost is:

- **Compute:** $0
- **VCN / subnet / route table / security list / IGW:** $0
- **Total target:** **$0**

Relevant Oracle references accessed on **2026-05-11**:

- Always Free overview:
  <https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm>
- Always Free resources reference:
  <https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm>
- OCI pricing overview:
  <https://www.oracle.com/cloud/pricing/>
- OCI price list:
  <https://www.oracle.com/cloud/price-list/>

### Important limit reminder

Oracle's Always Free guidance says Ampere A1 usage must stay within a total of
**4 OCPUs and 24 GB memory** across the tenancy. The single-node plan above is
sized exactly to that ceiling.

### If Always Free is not usable

If the tenancy cannot use the A1 Always Free path, use Oracle's current pricing
pages above before provisioning any paid fallback. Do not assume the fallback is
free.

## Teardown

Delete in reverse dependency order.

```bash
oci compute instance terminate \
  --instance-id "$INSTANCE_ID" \
  --force \
  --preserve-boot-volume false \
  --wait-for-state TERMINATED

oci network subnet delete \
  --subnet-id "$SUBNET_ID" \
  --force \
  --wait-for-state TERMINATED

oci network security-list delete \
  --security-list-id "$SL_ID" \
  --force \
  --wait-for-state TERMINATED

oci network route-table delete \
  --rt-id "$RT_ID" \
  --force \
  --wait-for-state TERMINATED

oci network internet-gateway delete \
  --ig-id "$IGW_ID" \
  --force \
  --wait-for-state TERMINATED

oci network vcn delete \
  --vcn-id "$VCN_ID" \
  --force \
  --wait-for-state TERMINATED
```

## chemsmart validation checklist

Run this only **after** the agent work from PR #85 / #86 (or equivalent local
branch state) is available in the chemsmart checkout.

### 1. Wizard render check

Do **not** auto-write config yet.

```bash
chemsmart agent wizard <name> --host <PUBLIC_IP>
```

Verify that the rendered YAML points to:

- the OCI VM public IP or DNS name
- the Slurm scheduler
- the intended remote scratch path (`/home/ubuntu/scratch`)
- the ORCA executable path actually installed on the node

### 2. Dry-submit check

```bash
chemsmart agent run \
  "single-point on examples/h2o.xyz at HF/STO-3G ORCA" \
  --dry-submit
```

Verify:

- the job plan selects ORCA, not Gaussian
- the submission target is Slurm, not SGE
- generated files and submit script look sane
- no remote execution happens yet

### 3. Execute check

Only after the wizard YAML has been reviewed and approved:

```bash
chemsmart agent run \
  "single-point on examples/h2o.xyz at HF/STO-3G ORCA" \
  --execute
```

Verify on the OCI node:

```bash
ssh -i "$SSH_KEY" ubuntu@"$PUBLIC_IP" 'squeue; sacct -X --format=JobID,State,Elapsed | tail'
```

Target result:

- Slurm accepts the job
- ORCA starts successfully
- chemsmart captures completion state end-to-end

### 4. Audit artifact check

Inspect the session audit trail:

```bash
ls -1 ~/.chemsmart/agent/sessions
SESSION_ID='<latest-session-id>'

jq -C . ~/.chemsmart/agent/sessions/"$SESSION_ID"/session_metadata.json | less -R
sed -n '1,200p' ~/.chemsmart/agent/sessions/"$SESSION_ID"/decision_log.jsonl
```

Expected checks:

- `decision_log.jsonl` exists and is append-only
- the log contains the request, planning, tool use, and submission decisions
- `session_metadata.json` records completion state for the run

## Open questions

1. **ORCA on Arm:** do you have a Linux Arm-compatible ORCA build, or should
   the plan switch to an x86-based node instead?
2. **Installer staging:** will ORCA be delivered by direct HTTPS URL, by OCI
   Object Storage pre-authenticated request URL, or by manual `scp` after boot?
3. **Compartment choice:** is the root compartment acceptable, or should a
   dedicated child compartment be created first?
4. **Region choice:** should this stay in `ap-chuncheon-1` for Always Free, or
   is there a reason to prefer `ap-seoul-1` despite the current subscription
   mismatch?
5. **Single node vs. two nodes:** is the one-node Slurm controller+worker good
   enough for validation, or do you want an optional second worker in the final
   provisioning runbook?
6. **SSH ingress policy:** confirm the source IP or CIDR that should replace
   `MY_IP/32` at launch time.

## External references

- Oracle Cloud Free Tier docs:
  <https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm>
- Oracle Always Free resources:
  <https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm>
- Oracle OCI pricing overview:
  <https://www.oracle.com/cloud/pricing/>
- Oracle OCI price list:
  <https://www.oracle.com/cloud/price-list/>
- ORCA 6.1 installation manual:
  <https://www.faccts.de/docs/orca/6.1/manual/contents/quickstartguide/installation.html>
- ORCA install tutorial:
  <https://www.faccts.de/docs/orca/6.1/tutorials/first_steps/install.html>
