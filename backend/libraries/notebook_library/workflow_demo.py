from synthesize_workflow import propose_workflow

outline = propose_workflow("download SST and plot annual anomaly", max_steps=6)
print(outline)
