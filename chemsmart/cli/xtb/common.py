"""Shared xTB CLI job construction."""


def build_xtb_jobs(ctx, job_cls, settings, skip_completed, kwargs):
    molecules = ctx.obj["molecules"]
    indices = ctx.obj["molecule_indices"]
    label = ctx.obj["label"]
    jobrunner = ctx.obj["jobrunner"]
    if len(molecules) > 1 and indices is not None:
        return [
            job_cls(
                molecule=molecule,
                settings=settings,
                label=f"{label}_idx{index}",
                jobrunner=jobrunner,
                skip_completed=skip_completed,
                **kwargs,
            )
            for molecule, index in zip(molecules, indices)
        ]
    return job_cls(
        molecule=molecules[-1],
        settings=settings,
        label=label,
        jobrunner=jobrunner,
        skip_completed=skip_completed,
        **kwargs,
    )
