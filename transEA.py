#coding:utf-8
import numpy as np
import tensorflow as tf
import os
import time
import datetime
import ctypes

ll = ctypes.cdll.LoadLibrary
lib = ll("./initEA.so")
test_lib = ll("./test.so")

class Config(object):

    def __init__(self):
        # lib.setInPath("data")
        # test_lib.setInPath("data")
        lib.showPath()
        # test_lib.showPath()
        self.testFlag = True
        self.loadFromData = True
        self.L1_flag = True
        self.hidden_size = 50
        self.nbatches = 100
        self.entity = 0
        self.relation = 0
        self.trainTimes = 3000
        self.margin = 4.0
        self.learning_rate = 0.001
        self.attribute = 0
        self.alpha = 0.6

class TransEModel(object):

    def __init__(self, config):

        entity_total = config.entity
        relation_total = config.relation
        batch_size = config.batch_size
        size = config.hidden_size
        margin = config.margin

        attribute_total = config.attribute
        batch_sizeA = config.batch_sizeA
        alpha = config.alpha

        self.pos_h = tf.placeholder(tf.int32, [None])
        self.pos_t = tf.placeholder(tf.int32, [None])
        self.pos_r = tf.placeholder(tf.int32, [None])

        self.neg_h = tf.placeholder(tf.int32, [None])
        self.neg_t = tf.placeholder(tf.int32, [None])
        self.neg_r = tf.placeholder(tf.int32, [None])

        self.e = tf.placeholder(tf.int32,[None])
        self.a = tf.placeholder(tf.int32,[None])
        self.v = tf.placeholder(tf.float32,[None])

        with tf.name_scope("embedding"):
            self.ent_embeddings = tf.get_variable(name = "ent_embedding", shape = [entity_total, size], initializer = tf.contrib.layers.xavier_initializer(uniform = True))
            self.rel_embeddings = tf.get_variable(name = "rel_embedding", shape = [relation_total, size], initializer = tf.contrib.layers.xavier_initializer(uniform = True))
            self.attr_embeddings = tf.get_variable(name = "attr_embedding", shape = [attribute_total, size], initializer = tf.contrib.layers.xavier_initializer(uniform = True))
            self.b = tf.get_variable(name = "bias", shape = [3994], initializer = tf.constant_initializer(0.01))


            ent_l2_norm = tf.sqrt(tf.reduce_sum(tf.square(self.ent_embeddings), 1, keep_dims = True))
            rel_l2_norm = tf.sqrt(tf.reduce_sum(tf.square(self.rel_embeddings), 1, keep_dims = True))
            attr_l2_norm = tf.sqrt(tf.reduce_sum(tf.square(self.attr_embeddings), 1, keep_dims = True))

            self.ent_embeddings = self.ent_embeddings / ent_l2_norm
            self.rel_embeddings = self.rel_embeddings / rel_l2_norm
            self.attr_embeddings = self.attr_embeddings / attr_l2_norm

            pos_h_e = tf.nn.embedding_lookup(self.ent_embeddings, self.pos_h)
            pos_t_e = tf.nn.embedding_lookup(self.ent_embeddings, self.pos_t)
            pos_r_e = tf.nn.embedding_lookup(self.rel_embeddings, self.pos_r)
            neg_h_e = tf.nn.embedding_lookup(self.ent_embeddings, self.neg_h)
            neg_t_e = tf.nn.embedding_lookup(self.ent_embeddings, self.neg_t)
            neg_r_e = tf.nn.embedding_lookup(self.rel_embeddings, self.neg_r)

            e_e = tf.nn.embedding_lookup(self.ent_embeddings, self.e)
            a_v = tf.nn.embedding_lookup(self.attr_embeddings, self.a)


        if config.L1_flag:
            pos = tf.reduce_sum(abs(pos_h_e + pos_r_e - pos_t_e), 1, keep_dims = True)
            neg = tf.reduce_sum(abs(neg_h_e + neg_r_e - neg_t_e), 1, keep_dims = True)
            self.predict = pos
        else:
            pos = tf.reduce_sum((pos_h_e + pos_r_e - pos_t_e) ** 2, 1, keep_dims = True)
            neg = tf.reduce_sum((neg_h_e + neg_r_e - neg_t_e) ** 2, 1, keep_dims = True)
            self.predict = pos

        with tf.name_scope("output"):
            aV = tf.reduce_sum(a_v * e_e, axis = 1)
            target = aV + self.b - self.v
            attr_loss = tf.reduce_sum(abs(target), keep_dims = True)
            rel_loss = tf.reduce_sum(tf.maximum(pos - neg + margin, 0))
            self.loss = alpha * attr_loss + (1 - alpha) * rel_loss


def main(_):
    config = Config()
    if (config.testFlag):
        test_lib.init()
        config.relation = test_lib.getRelationTotal()
        config.entity = test_lib.getEntityTotal()
        config.batch = test_lib.getEntityTotal()
        config.batch_size = config.batch
        config.batch_sizeA = config.batch
        config.attribute = 25

    else:
        lib.init()
        config.relation = lib.getRelationTotal()
        config.entity = lib.getEntityTotal()
        config.batch_size = lib.getTripleTotal() // config.nbatches
        config.attribute = lib.getAttrTotal()
        config.batch_sizeA = lib.getAttpTotal() // config.nbatches

    with tf.Graph().as_default():
        path = './model/YG/EA/L1_50_4_0.01/'
        sess = tf.Session()
        with sess.as_default():
            initializer = tf.contrib.layers.xavier_initializer(uniform = False)
            with tf.variable_scope("model", reuse=None, initializer = initializer):
                trainModel = TransEModel(config = config)

            global_step = tf.Variable(0, name="global_step", trainable=False)
            optimizer = tf.train.GradientDescentOptimizer(config.learning_rate)
            grads_and_vars = optimizer.compute_gradients(trainModel.loss)
            train_op = optimizer.apply_gradients(grads_and_vars, global_step=global_step)
            saver = tf.train.Saver()
            sess.run(tf.global_variables_initializer())

            def train_step(e_batch, a_batch, v_batch, pos_h_batch, pos_t_batch, pos_r_batch, neg_h_batch, neg_t_batch, neg_r_batch):
                feed_dict = {
                    trainModel.e: e_batch,
                    trainModel.a: a_batch,
                    trainModel.v: v_batch,
                    trainModel.pos_h: pos_h_batch,
                    trainModel.pos_t: pos_t_batch,
                    trainModel.pos_r: pos_r_batch,
                    trainModel.neg_h: neg_h_batch,
                    trainModel.neg_t: neg_t_batch,
                    trainModel.neg_r: neg_r_batch
                }
                _, step, loss = sess.run(
                    [train_op, global_step, trainModel.loss], feed_dict)
                return loss

            def test_step(pos_h_batch, pos_t_batch, pos_r_batch):
                feed_dict = {
                    trainModel.pos_h: pos_h_batch,
                    trainModel.pos_t: pos_t_batch,
                    trainModel.pos_r: pos_r_batch,
                }
                step, predict = sess.run(
                    [global_step, trainModel.predict], feed_dict)
                return predict

            ph = np.zeros(config.batch_size, dtype = np.int32)
            pt = np.zeros(config.batch_size, dtype = np.int32)
            pr = np.zeros(config.batch_size, dtype = np.int32)
            nh = np.zeros(config.batch_size, dtype = np.int32)
            nt = np.zeros(config.batch_size, dtype = np.int32)
            nr = np.zeros(config.batch_size, dtype = np.int32)

            ph_addr = ph.__array_interface__['data'][0]
            pt_addr = pt.__array_interface__['data'][0]
            pr_addr = pr.__array_interface__['data'][0]
            nh_addr = nh.__array_interface__['data'][0]
            nt_addr = nt.__array_interface__['data'][0]
            nr_addr = nr.__array_interface__['data'][0]

            e = np.zeros(config.batch_size, dtype = np.int32)
            a = np.zeros(config.batch_size, dtype = np.int32)
            v = np.zeros(config.batch_size, dtype = np.float64)

            e_addr = e.__array_interface__['data'][0]
            a_addr = a.__array_interface__['data'][0]
            v_addr = v.__array_interface__['data'][0]

            lib.getBatch.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
            lib.getAttrBatch.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
            test_lib.getHeadBatch.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            test_lib.getTailBatch.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            test_lib.testHead.argtypes = [ctypes.c_void_p]
            test_lib.testTail.argtypes = [ctypes.c_void_p]

            if not config.testFlag:
                for times in range(config.trainTimes):
                    res = 0.0
                    for batch in range(config.nbatches):
                        lib.getAttrBatch(e_addr, a_addr, v_addr, config.batch_size)
                        lib.getBatch(ph_addr, pt_addr, pr_addr, nh_addr, nt_addr, nr_addr, config.batch_size)
                        res += train_step(e,a,v,ph, pt, pr, nh, nt, nr)
                        current_step = tf.train.global_step(sess, global_step)
                    print (times) 
                    print (res)
                if not os.path.exists(path):
                    os.makedirs(path)
                saver.save(sess, path + 'model.vec',global_step = global_step)

            else:
                if (config.loadFromData):
                    ckpt = tf.train.get_checkpoint_state(path)
                    if ckpt and ckpt.model_checkpoint_path:
                        for i in ckpt.all_model_checkpoint_paths:
                            saver.restore(sess,i)
                            total = test_lib.getTestTotal()
                            for times in range(total):
                                test_lib.getHeadBatch(ph_addr, pt_addr, pr_addr)
                                res = test_step(ph, pt, pr)
                                test_lib.testHead(res.__array_interface__['data'][0])

                                test_lib.getTailBatch(ph_addr, pt_addr, pr_addr)
                                res = test_step(ph, pt, pr)
                                test_lib.testTail(res.__array_interface__['data'][0])
                                # print (times)
                                if (times % 50 == 0):
                                    test_lib.test()
                            test_lib.test()

if __name__ == "__main__":
    tf.app.run()
