"""D' (d-prime) Sensitivity Index"""

# Authors: Nicolas Pinto <nicolas.pinto@gmail.com>
#          Nicolas Poilvert <nicolas.poilvert@gmail.com>
#          Ha Hong <hahong84@gmail.com>
#
# License: BSD

__all__ = ['dprime', 'dprime_from_samp', 'dprime_from_confusion']

import numpy as np
from scipy.stats import norm

DEFAULT_FUDGE_FACTOR = 0.5
DEFAULT_FUDGE_MODE = 'correction'


def dprime(y_pred, y_true, **kwargs):
    """Computes the d-prime sensitivity index of the predictions.

    Parameters
    ----------
    y_true: array, shape = [n_samples]
        True values, interpreted as strictly positive or not
        (i.e. converted to binary).
        Could be in {-1, +1} or {0, 1} or {False, True}.

    y_pred: array, shape = [n_samples]
        Predicted values (real).

    kwargs: named arguments, optional
        Passed to ``dprime_from_samp()``.

    Returns
    -------
    dp: float
        d-prime

    References
    ----------
    http://en.wikipedia.org/wiki/D'
    """

    # -- basic checks and conversion
    assert len(y_true) == len(y_pred)
    assert np.isfinite(y_true).all()
    assert np.isfinite(y_pred).all()

    y_true = np.array(y_true)
    assert y_true.ndim == 1

    y_pred = np.array(y_pred)
    assert y_pred.ndim == 1

    # -- actual computation
    i_pos = y_true > 0
    i_neg = ~i_pos

    pos = y_pred[i_pos]
    neg = y_pred[i_neg]

    dp = dprime_from_samp(pos, neg, **kwargs)
    return dp


def dprime_from_samp(pos, neg, max_value=np.inf, min_value=-np.inf):
    """Computes the d-prime sensitivity index from positive and negative samples.

    Parameters
    ----------
    pos: array-like
        Positive sample values (e.g., raw projection values of the positive classifier).

    neg: array-like
        Negative sample values.

    max_value: float, optional
        Maximum possible d-prime value. Default is ``np.inf``.

    min_value: float, optional
        Minimum possible d-prime value. Default is ``-np.inf``.

    Returns
    -------
    dp: float
        d-prime

    References
    ----------
    http://en.wikipedia.org/wiki/D'
    """

    pos = np.array(pos)
    neg = np.array(neg)

    if pos.size <= 1:
        raise ValueError('Not enough positive samples to estimate the variance')
    if neg.size <= 1:
        raise ValueError('Not enough negative samples to estimate the variance')

    pos_mean = pos.mean()
    neg_mean = neg.mean()
    pos_var = pos.var(ddof=1)
    neg_var = neg.var(ddof=1)

    num = pos_mean - neg_mean
    div = np.sqrt((pos_var + neg_var) / 2.)

    # from Dan's suggestion about clipping d' values...
    dp = np.clip(num / div, min_value, max_value)

    return dp


def dprime_from_confusion(M, collation=None, fudge_mode=DEFAULT_FUDGE_MODE, \
        fudge_factor=DEFAULT_FUDGE_FACTOR, max_value=np.inf, min_value=-np.inf):
    """Computes the d-prime sensitivity index of the confusion matrix.
    This function is mostly for when there is no access to internal representation 
    and/or decision making (like human data).

    Parameters
    ----------
    M: array-like, shape = [n_classes (true), n_classes (pred)] 
        Confusion matrix, where the element M_{rc} means the number of
        times when the classifier guesses that a test sample in the r-th class
        belongs to the c-th class.

    collation: None or array-like with shape = [n_groupings, n_classes], optional
        Defines how to group entries in `M` to compute TPR and FPR.  
        Entries shoule be {+1, 0, -1}.  A row defines one instance of grouping,
        where +1, -1, and 0 designate the corresponding class as a
        positive, negative, and ignored class, respectively.  For example, 
        the following `collation` defines a 3-way one vs. rest grouping 
        (given that `M` is a 3x3 matrix):
            [[+1, -1, -1],
             [-1, +1, -1],
             [-1, -1, +1]]
        If `None` (default), one vs. rest grouping is assumed.

    fudge_factor: float, optional
        A small factor to avoid non-finite numbers when TPR or FPR becomes 0 or 1.
        Default is 0.5.

    fudge_mode: str, optional
        Determins how to apply the fudge factor.  Can be one of:
            'correction': apply only when needed (default)
            'always': always apply the fudge factor
            'none': no fudging --- equivalent to ``fudge_factor=0``

    max_value: float, optional
        Maximum possible d-prime value. Default is ``np.inf``.

    min_value: float, optional
        Minimum possible d-prime value. Default is ``-np.inf``.


    Returns
    -------
    dp: array, shape = [n_groupings]
        Array of d-primes, where each element corresponds to each grouping
        defined by `collation`.

    References
    ----------
    http://en.wikipedia.org/wiki/D'
    http://en.wikipedia.org/wiki/Confusion_matrix
    """

    # M: confusion matrix, row means true classes, col means predicted classes
    M = np.array(M)
    assert M.ndim == 2
    assert M.shape[0] == M.shape[1]
    n_classes = M.shape[0]

    if collation is None:    
        # make it one vs. rest
        collation = -np.ones((n_classes, n_classes), dtype='int8')
        collation += 2 * np.eye(n_classes, dtype='int8')
    else:
        collation = np.array(collation, dtype='int8')
        assert collation.ndim == 2
        assert collation.shape[1] == n_classes
    
    # P0: number of positives, for each class
    # P: number of positives, for each grouping
    # N: number of negatives, for each grouping
    # TP: number of true positives, for each grouping
    # FP: number of false positives, for each grouping
    P0 = np.sum(M, axis=1)   
    P = np.array([np.sum(P0[coll == +1]) for coll in collation], dtype='float64')
    N = np.array([np.sum(P0[coll == -1]) for coll in collation], dtype='float64')
    TP = np.array([np.sum(M[coll == +1][:, coll == +1]) for coll in collation], dtype='float64')
    FP = np.array([np.sum(M[coll == -1][:, coll == +1]) for coll in collation], dtype='float64')

    # -- application of fudge factor
    if fudge_mode == 'none':           # no fudging
        pass

    elif fudge_mode == 'always':       # always apply fudge factor
        TP += fudge_factor
        FP += fudge_factor
        P += 2.*fudge_factor
        N += 2.*fudge_factor

    elif fudge_mode == 'correction':   # apply fudge factor only when needed
        TP[TP == P] = P[TP == P] - fudge_factor    # 100% correct
        TP[TP == 0] = fudge_factor                 # 0% correct
        FP[FP == N] = N[FP == N] - fudge_factor    # always FAR
        FP[FP == 0] = fudge_factor                 # no false alarm

    else:
        raise ValueError('Invalid fudge_mode')

    # -- done. compute the d'
    TPR = TP / P
    FPR = FP / N
    dp = np.clip(norm.ppf(TPR) - norm.ppf(FPR), min_value, max_value)

    return dp

