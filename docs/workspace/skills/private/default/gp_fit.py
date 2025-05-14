"""
Gaussian Process fitting and visualization module.

This module provides functions for fitting Gaussian Process regression models
to noisy data and visualizing the results.
"""

import matplotlib.pyplot as plt
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF
from sklearn.gaussian_process.kernels import ConstantKernel as C


def gp_fit(X_samples, y_samples, X_pred=None, alpha=0.1, n_restarts=15):
    """
    Fit a Gaussian Process regression model to input samples and make predictions.

    Parameters
    ----------
    X_samples : array-like, shape (n_samples, n_features)
        Training data input features
    y_samples : array-like, shape (n_samples,)
        Training data target values (noisy observations)
    X_pred : array-like, shape (n_pred, n_features), optional
        Prediction input points. If None, uses a fine grid based on X_samples range.
    alpha : float, default=0.1
        Noise level parameter for the Gaussian Process
    n_restarts : int, default=15
        Number of optimizer restarts to find optimal kernel parameters

    Returns
    -------
    dict
        A dictionary containing:
        - 'X_pred': The prediction input points
        - 'y_pred': The mean predictions
        - 'sigma': Standard deviation of predictions (uncertainty)
        - 'gp': The fitted GaussianProcessRegressor object
    """
    # Define the kernel
    kernel = C(1.0, (1e-3, 1e3)) * RBF(1.0, (1e-2, 1e2))

    # Create and fit the Gaussian Process model
    gp = GaussianProcessRegressor(kernel=kernel, alpha=alpha, n_restarts_optimizer=n_restarts)
    gp.fit(X_samples, y_samples)

    # Generate prediction points if not provided
    if X_pred is None:
        X_min, X_max = X_samples.min(), X_samples.max()
        X_pred = np.linspace(X_min, X_max, 100).reshape(-1, 1)

    # Make predictions
    y_pred, sigma = gp.predict(X_pred, return_std=True)

    return {"X_pred": X_pred, "y_pred": y_pred, "sigma": sigma, "gp": gp}


def plot_pred(X_true, y_true, X_samples, y_samples, gp_results, title="Gaussian Process Regression"):
    """
    Plot the original function, noisy samples, and Gaussian Process predictions.

    Parameters
    ----------
    X_true : array-like
        X values for the true function
    y_true : array-like
        Y values for the true function
    X_samples : array-like
        X values of the noisy samples
    y_samples : array-like
        Y values of the noisy samples
    gp_results : dict
        Dictionary returned by gp_fit function containing prediction results
    title : str, default='Gaussian Process Regression'
        Plot title

    Returns
    -------
    matplotlib.figure.Figure
        The generated matplotlib figure
    """
    X_pred = gp_results["X_pred"]
    y_pred = gp_results["y_pred"]
    sigma = gp_results["sigma"]

    fig = plt.figure(figsize=(10, 6))

    # Plot the noisy samples
    plt.scatter(X_samples, y_samples, color="red", label="Noisy samples")

    # Plot the true function if provided
    if X_true is not None and y_true is not None:
        plt.plot(X_true, y_true, "b-", label="True function")

    # Plot the GP prediction and its confidence interval
    plt.plot(X_pred, y_pred, "k-", label="GP prediction")
    plt.fill_between(
        X_pred.ravel(),
        y_pred - 1.96 * sigma,
        y_pred + 1.96 * sigma,
        alpha=0.2,
        color="k",
        label="95% confidence interval",
    )

    plt.title(title)
    plt.xlabel("x")
    plt.ylabel("y")
    plt.legend()
    plt.grid(True)

    return fig
