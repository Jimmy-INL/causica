"""
Wrapper around torch.distributions.transforms to allow for joint transforms on TensorDicts.
"""

import torch
import torch.distributions as td
from tensordict import TensorDict


class JointTransform(td.Transform):
    """A joint transform that applies a different transform to each key in the TensorDict.

    This is heavily inspired by the `torch.distributions.transforms.StackTransform` class.
    See https://pytorch.org/docs/stable/distributions.html#torch.distributions.transforms.StackTransform
    """

    def __init__(self, transformations: dict[str, td.Transform], cache_size: int = 0):
        """
        Args:
            transformations: A dictionary of transforms, where the keys are the keys in the TensorDict
            cache_size: Size of cache. If zero, no caching is done. If one, the latest single value is cached.
                Only 0 and 1 are supported.
        """
        assert all(
            isinstance(t, td.Transform) for t in transformations.values()
        ), f"All transformations must be of type torch.distributions.Transform, but are {[type(t) for t in transformations.values()]}."
        if cache_size:
            transformations = {key: t.with_cache(cache_size) for key, t in transformations.items()}
        super().__init__(cache_size=cache_size)

        self.transformations = transformations

    def _call(self, x: TensorDict) -> TensorDict:
        if not set(self.transformations.keys()).issubset(x.keys()):
            raise ValueError("All keys in transformations must be in x.")

        return x.clone().update({key: transform(x[key]) for key, transform in self.transformations.items()})

    def _inverse(self, y: TensorDict) -> TensorDict:
        # We cannot use ._inv as pylint complains with E202: _inv is hidden because of `self._inv = None`
        # in td.Transform.__init__
        if not set(self.transformations.keys()).issubset(y.keys()):
            raise ValueError("All keys in transformations must be in y.")

        return y.clone().update({key: transform.inv(y[key]) for key, transform in self.transformations.items()})

    def log_abs_det_jacobian(self, x: TensorDict, y: TensorDict) -> torch.Tensor:
        if set(x.keys()) != set(y.keys()):
            raise ValueError("x and y must have the same keys.")

        if not set(self.transformations.keys()).issubset(x.keys()):
            raise ValueError("All keys in transformations must be in x and y.")

        return x.clone().update(
            {
                key: self.transformations[key].log_abs_det_jacobian(x[key], y[key])
                if key in self.transformations
                else torch.ones_like(x[key])
                for key in x.keys()
            }
        )

    @property
    def bijective(self):
        return all(t.bijective for t in self.transformations.values())

    @property
    def domain(self):
        return {key: t.domain for key, t in self.transformations.items()}

    @property
    def codomain(self):
        return {key: t.codomain for key, t in self.transformations.items()}
