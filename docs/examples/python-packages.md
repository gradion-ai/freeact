# Data analysis

Freeact can use any Python package available in the execution environment. This example demonstrates using scikit-learn and matplotlib directly in code actions to fit a Gaussian Process Regressor to noisy sine wave data and visualize the results with uncertainty bounds.

Create a [workspace with a virtual environment](../installation.md#option-2-with-virtual-environment) and install the required dependencies:

```bash
uv pip install scikit-learn matplotlib
```

Start the [CLI tool](../cli.md):

```bash
uv run freeact
```

In the screenshot [below](#recording), the agent performs Gaussian Process Regression in response to a single prompt:

> Generate 30 noisy samples from a sine function and fit a Gaussian process regressor to the data. Save the result as a plot with uncertainty bounds to output/gpr_sine.png.

The agent generates the samples, fits a `GaussianProcessRegressor` with an RBF kernel, and creates a [visualization](#result-plot) showing the true sine function, noisy samples, model predictions, and uncertainty bounds.

A follow-up prompt asks for model statistics:

> print the stats

The agent prints the log-marginal-likelihood and other attributes from the fitted model.

[![Python Packages](../screenshots/python-packages.png)](../screenshots/python-packages.png){ target="_blank" rel="noopener" #recording}

The resulting plot shows the GPR fit with a confidence interval:

![Gaussian Process Regression on Noisy Sine Wave](../images/gpr_sine.png){#result-plot}
