import unittest

import numpy as np

from pcdoctor import dataset, metrics
from pcdoctor.classifier import KNN, ExpertBayes, NaiveBayes
from pcdoctor.knowledge_base import KnowledgeBase


class DatasetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase.load()
        cls.X, cls.y = dataset.generate(cls.kb, n_samples=1200, seed=1)

    def test_shape(self):
        self.assertEqual(self.X.shape, (1200, 20))
        self.assertTrue((self.X.sum(axis=1) >= 2).all())
        self.assertEqual(len(np.unique(self.y)), 8)

    def test_split_stratified(self):
        X_tr, X_te, y_tr, y_te = dataset.train_test_split(self.X, self.y, 0.25)
        self.assertEqual(len(y_tr) + len(y_te), 1200)
        for c in range(8):
            share = (y_te == c).sum() / (self.y == c).sum()
            self.assertAlmostEqual(share, 0.25, delta=0.02)

    def test_naive_bayes(self):
        X_tr, X_te, y_tr, y_te = dataset.train_test_split(self.X, self.y)
        nb = NaiveBayes().fit(X_tr, y_tr, 8)
        self.assertGreater(metrics.accuracy(y_te, nb.predict(X_te)), 0.75)
        self.assertTrue(np.allclose(nb.predict_proba(X_te).sum(axis=1), 1))

    def test_expert_and_knn(self):
        self.assertGreater(metrics.accuracy(self.y, ExpertBayes(self.kb).predict(self.X)), 0.75)
        knn = KNN(7).fit(self.X[:900], self.y[:900])
        self.assertGreater(metrics.accuracy(self.y[900:], knn.predict(self.X[900:])), 0.7)

    def test_posterior_partial(self):
        nb = ExpertBayes(self.kb)
        idx = self.kb.symptom_ids.index
        post = nb.posterior({idx("clicking_sound"): 1, idx("files_corrupted"): 1})
        self.assertEqual(self.kb.fault_ids[post.argmax()], "disk_failure")

    def test_metrics(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 1, 1, 1])
        cm = metrics.confusion_matrix(y_true, y_pred, 2)
        self.assertEqual(cm.tolist(), [[1, 1], [0, 2]])
        p, r, f1 = metrics.precision_recall_f1(cm)
        self.assertAlmostEqual(p[1], 2 / 3)
        self.assertAlmostEqual(r[0], 0.5)


if __name__ == "__main__":
    unittest.main()
