import unittest

import chainer
from chainer import cuda
from chainer import testing
from chainer.testing import condition
from chainer.testing import attr
import numpy

from chainerrl.links import noisy_linear


def get_xp_from_id(gpu):
    if gpu >= 0:
        return cuda.cupy
    else:
        return numpy


@testing.parameterize(*testing.product({
    'size_args': [
        (5,),  # uninitialized from Chainer v2
        (None, 5),  # uninitialized
        (6, 5),  # initialized
    ],
    'nobias': [False, True],
}))
class TestFactorizedNoisyLinear(unittest.TestCase):
    def setUp(self):
        mu = chainer.links.Linear(*self.size_args, nobias=self.nobias)
        self.l = noisy_linear.FactorizedNoisyLinear(mu)

    def _test_calls(self, gpu):
        xp = get_xp_from_id(gpu)
        if gpu >= 0:
            self.l.to_gpu(gpu)

        x_data = xp.arange(12).astype(numpy.float32).reshape((2, 6))
        x = chainer.Variable(x_data)
        self.l(x)
        self.l(x_data + 1)
        self.l(x_data.reshape((2, 3, 2)))

    def test_calls_cpu(self):
        self._test_calls(gpu=-1)

    @attr.gpu
    def test_calls_gpu(self):
        self._test_calls(gpu=0)

    def _test_randomness(self, gpu):
        xp = get_xp_from_id(gpu)
        if gpu >= 0:
            self.l.to_gpu(gpu)

        x = xp.random.standard_normal((10, 6)).astype(numpy.float32)
        y1 = self.l(x).data
        y2 = self.l(x).data
        d = float(xp.mean(xp.square(y1 - y2)))

        # The parameter name suggests that
        # xp.sqrt(d / 2) is approx to sigma_scale = 0.4
        # In fact, (for each element _[i, j],) it holds:
        # \E[(y2 - y1) ** 2] = 2 * \Var(y) = (4 / pi) * sigma_scale ** 2

        target = (0.4 ** 2) * 2
        if self.nobias:
            target *= 2 / numpy.pi
        else:
            target *= 2 / numpy.pi + numpy.sqrt(2 / numpy.pi)

        self.assertGreater(d, target / 3.)
        self.assertLess(d, target * 3.)

    @condition.retry(3)
    def test_randomness_cpu(self):
        self._test_randomness(gpu=-1)

    @attr.gpu
    @condition.retry(3)
    def test_randomness_gpu(self):
        self._test_randomness(gpu=0)

    def _test_non_randomness(self, gpu):
        xp = get_xp_from_id(gpu)
        if gpu >= 0:
            self.l.to_gpu(gpu)

        # Noises should be the same in a batch
        x0 = xp.random.standard_normal((1, 6)).astype(numpy.float32)
        x = xp.broadcast_to(x0, (2, 6))
        y = self.l(x).data
        xp.testing.assert_allclose(y[0], y[1], rtol=1e-4)

    def test_non_randomness_cpu(self):
        self._test_non_randomness(gpu=-1)

    @attr.gpu
    def test_non_randomness_gpu(self):
        self._test_non_randomness(gpu=0)
