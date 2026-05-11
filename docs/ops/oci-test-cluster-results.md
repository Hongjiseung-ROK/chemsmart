# OCI test cluster results

Date: 2026-05-11  
Region: `ap-chuncheon-1`  
Compartment: tenancy root  
Outcome: **STOPPED at step 6** (`oci compute instance launch`) per task instruction to stop on any OCI create failure.

## Summary

I completed the preflight, SSH key creation, image discovery, cloud-init authoring, and network provisioning for the OCI Always Free single-node Slurm target.

The run stopped on the first compute create attempt. I did **not** retry the failed create.

## Exact create failure

Command attempted:

```bash
oci compute instance launch \
  --region ap-chuncheon-1 \
  --compartment-id ocid1.tenancy.oc1..aaaaaaaabp4dih3ybtil4qjoxchz33sjd22kih6u5ov5eq4rffwpwapxlt5a \
  --availability-domain HdoO:AP-CHUNCHEON-1-AD-1 \
  --display-name chemsmart-slurm-head \
  --hostname-label chemslurm1 \
  --shape VM.Standard.A1.Flex \
  --shape-config '{"ocpus":4,"memoryInGBs":24}' \
  --subnet-id ocid1.subnet.oc1.ap-chuncheon-1.aaaaaaaayekt2uqlqzcgxoubgq6dsvabsvpg7vbq52fjezt5twpak3shgmta \
  --assign-public-ip true \
  --image-id ocid1.image.oc1.ap-chuncheon-1.aaaaaaaauvxjy5tclxvl5nz34arovhumdt37bctdqf23sjuqrlr24vuthkvq \
  --boot-volume-size-in-gbs 100 \
  --ssh-authorized-keys-file ~/.ssh/chemsmart-slurm_ed25519.pub \
  --user-data-file /tmp/chemsmart-cloud-init.yaml \
  --wait-for-state RUNNING
```

OCI CLI error:

```text
RequestException:
{
    "client_version": "Oracle-PythonCLI/3.81.1",
    "logging_tips": "Please run the OCI CLI command using --debug flag to find more debug information.",
    "message": "The connection to endpoint timed out.",
    "request_endpoint": null,
    "target_service": "CLI",
    "timestamp": "2026-05-11T11:19:44.420906",
    "troubleshooting_tips": " See [https://docs.oracle.com/iaas/Content/API/SDKDocs/clitroubleshooting.htm] for more information about resolving this error. If you are unable to resolve this issue, run this CLI command with --debug option and contact Oracle support and provide them the full error message."
}
```

Post-failure read-only verification showed **no matching instance was created**, so there is no `INSTANCE_ID` and no `PUBLIC_IP`.

## Preflight facts

- Editable install path check passed: `/Users/hongjiseung/developer/chemsmart`
- IAM region-subscription re-check passed in `ap-chuncheon-1`
- Availability domain used: `HdoO:AP-CHUNCHEON-1-AD-1`
- Ubuntu 22.04 image selected: `ocid1.image.oc1.ap-chuncheon-1.aaaaaaaauvxjy5tclxvl5nz34arovhumdt37bctdqf23sjuqrlr24vuthkvq`
- SSH ingress source locked to: `112.171.21.152/32`
- SSH key created: `~/.ssh/chemsmart-slurm_ed25519`
- Cloud-init authored at: `/tmp/chemsmart-cloud-init.yaml`

## Rendered YAML

Wizard YAML was **not produced** because the live host was never created.

```yaml
# Not available.
# chemsmart agent wizard chemslurm1 --host ubuntu@<PUBLIC_IP>
# was not run because OCI instance launch failed and no PUBLIC_IP existed.
```

## Verification

| Criterion | Status | Notes |
| --- | --- | --- |
| `SCHEDULER: SLURM` | FAIL | Wizard not run; no rendered YAML. |
| `QUEUE_NAME: debug` | FAIL | Wizard not run; no rendered YAML. |
| `NUM_CORES: 4` | FAIL | Wizard not run; no rendered YAML. |
| `NUM_GB_MEM: 23` or `24` | FAIL | Wizard not run; no rendered YAML. |
| `SCRATCH_DIR: /home/ubuntu/scratch` | FAIL | Host not created; runtime not verified. |
| `GAUSSIAN.EXEFOLDER` null / source=`none` | FAIL | Wizard not run; no rendered YAML. |
| `ORCA.EXEFOLDER` null / source=`none` | FAIL | Wizard not run; no rendered YAML. |
| `CONDA_ENV` multi-line activate block | FAIL | Wizard not run; no rendered YAML. |

## Bugs surfaced

### chemsmart wizard bugs

- None surfaced in this run because the wizard was never executed.

### Non-wizard issues encountered

- Required reading path from task was missing locally: `/Users/hongjiseung/.agent-orchestrator/projects/chemsmart/worktrees/cs-orchestrator/bin/plan.md`
- OCI CLI create failed with a client-side timeout before any instance was observable via read-only list calls.

## OCI resource IDs created

- `VCN_ID`: `ocid1.vcn.oc1.ap-chuncheon-1.amaaaaaat42mauaaz26fdpc3zsom37m35sfqnsripypnhs3msnwfooij5wga`
- `IGW_ID`: `ocid1.internetgateway.oc1.ap-chuncheon-1.aaaaaaaak5dl3m72nbevow7gx6w4b4rf4pgpobw3zrd632ic3qcrbmypovbq`
- `RT_ID`: `ocid1.routetable.oc1.ap-chuncheon-1.aaaaaaaavixaouceszlkcwt6neeonjv5ggn4nxp76vvoebhm53es46bcxyrq`
- `SL_ID`: `ocid1.securitylist.oc1.ap-chuncheon-1.aaaaaaaadv5y3cawdhlwvvfta3xboyvk6eac7oze76txcyjqaaplqm57pjza`
- `SUBNET_ID`: `ocid1.subnet.oc1.ap-chuncheon-1.aaaaaaaayekt2uqlqzcgxoubgq6dsvabsvpg7vbq52fjezt5twpak3shgmta`
- `INSTANCE_ID`: not created

## Access details

- `PUBLIC_IP`: not assigned
- SSH command: unavailable (no instance)

## Teardown commands

```bash
export OCI_CLI_AUTH=security_token
export OCI_REGION=ap-chuncheon-1

oci network subnet delete \
  --region "$OCI_REGION" \
  --subnet-id ocid1.subnet.oc1.ap-chuncheon-1.aaaaaaaayekt2uqlqzcgxoubgq6dsvabsvpg7vbq52fjezt5twpak3shgmta \
  --force \
  --wait-for-state TERMINATED

oci network security-list delete \
  --region "$OCI_REGION" \
  --security-list-id ocid1.securitylist.oc1.ap-chuncheon-1.aaaaaaaadv5y3cawdhlwvvfta3xboyvk6eac7oze76txcyjqaaplqm57pjza \
  --force \
  --wait-for-state TERMINATED

oci network route-table delete \
  --region "$OCI_REGION" \
  --rt-id ocid1.routetable.oc1.ap-chuncheon-1.aaaaaaaavixaouceszlkcwt6neeonjv5ggn4nxp76vvoebhm53es46bcxyrq \
  --force \
  --wait-for-state TERMINATED

oci network internet-gateway delete \
  --region "$OCI_REGION" \
  --ig-id ocid1.internetgateway.oc1.ap-chuncheon-1.aaaaaaaak5dl3m72nbevow7gx6w4b4rf4pgpobw3zrd632ic3qcrbmypovbq \
  --force \
  --wait-for-state TERMINATED

oci network vcn delete \
  --region "$OCI_REGION" \
  --vcn-id ocid1.vcn.oc1.ap-chuncheon-1.amaaaaaat42mauaaz26fdpc3zsom37m35sfqnsripypnhs3msnwfooij5wga \
  --force \
  --wait-for-state TERMINATED
```
