import numpy as np
from helper.load_data import Data
from time import time
import scipy.sparse as sp
import random as rd
import collections

class JPPREC_loader(Data):
    def __init__(self, args, path):
        super().__init__(args, path)
      
        self.adj_list, self.adj_r_list = self._get_relational_adj_list()     
        self.lap_list = self._get_relational_lap_list()
        self.all_item_dict = self._get_all_item_dict()
        self.all_h_list, self.all_r_list, self.all_t_list, self.all_v_list = self._get_all_item_data()
     

    def _get_relational_adj_list(self):
        t1 = time()
        adj_mat_list = []
        adj_r_list = []

        def _np_mat2sp_adj(np_mat, row_pre, col_pre):
            n_all = self.n_users + self.n_items
            a_rows = np_mat[:, 0] + row_pre
            a_cols = np_mat[:, 1] + col_pre
            a_vals = [1.] * len(a_rows)

            b_rows = a_cols
            b_cols = a_rows
            b_vals = [1.] * len(b_rows)

            a_adj = sp.coo_matrix((a_vals, (a_rows, a_cols)), shape=(n_all, n_all))
            b_adj = sp.coo_matrix((b_vals, (b_rows, b_cols)), shape=(n_all, n_all))

            return a_adj, b_adj
        def _np_mat2sp_adj_S(np_mat, row_pre, col_pre):
            n_all = self.n_users + self.n_items
         
            a_rows = np_mat[:, 0] + row_pre
            a_cols = np_mat[:, 1] + col_pre
            a_vals = [1.] * len(a_rows)
            a_adj = sp.coo_matrix((a_vals, (a_rows, a_cols)), shape=(n_all, n_all))           
            return a_adj
        R, R_inv = _np_mat2sp_adj(self.train_data, row_pre=0, col_pre=self.n_users)
        P, P_inv = _np_mat2sp_adj(self.ptc_data, row_pre=0, col_pre=self.n_users)
        I, I_inv = _np_mat2sp_adj(self.ini_data, row_pre=0, col_pre=self.n_users)
        
        S = _np_mat2sp_adj_S(self.trust_data, row_pre=0, col_pre=0)
       
        adj_mat_list.append(I)
        adj_r_list.append(0)
        adj_mat_list.append(P)
        adj_r_list.append(1)
        adj_mat_list.append(S)
        adj_r_list.append(2)
        adj_mat_list.append(I_inv)
        adj_r_list.append(3)
        adj_mat_list.append(P_inv)
        adj_r_list.append(4)


        print('\tconvert %d relational triples into adj mat done. @%.4fs' %(len(adj_mat_list), time()-t1))
        print('relation adj list',adj_r_list)
        self.n_relations = len(adj_r_list)

        return adj_mat_list, adj_r_list

    def _get_relational_lap_list(self):
        def _bi_norm_lap(adj):
            rowsum = np.array(adj.sum(1))

            d_inv_sqrt = np.power(rowsum, -0.5).flatten()
            d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
            d_mat_inv_sqrt = sp.diags(d_inv_sqrt)

            bi_lap = adj.dot(d_mat_inv_sqrt).transpose().dot(d_mat_inv_sqrt)
            return bi_lap.tocoo()

        def _si_norm_lap(adj):
            rowsum = np.array(adj.sum(1))

            d_inv = np.power(rowsum, -1).flatten()
           
            d_inv[np.isinf(d_inv)] = 0.
            d_mat_inv = sp.diags(d_inv)

            norm_adj = d_mat_inv.dot(adj)
            return norm_adj.tocoo()

        if self.args.adj_type == 'bi':
            lap_list = [_bi_norm_lap(adj) for adj in self.adj_list]
            print('\tgenerate bi-normalized adjacency matrix.')
        elif self.args.adj_type == 'ngcf':
            lap_list = [_bi_norm_lap(adj) for adj in self.adj_list]
            print('\tgenerate bi-normalized adjacency matrix.')
        else:
            lap_list = [_si_norm_lap(adj) for adj in self.adj_list]
            print('\tgenerate si-normalized adjacency matrix.')
        return lap_list 

    def _get_all_item_dict(self):
        all_item_dict = collections.defaultdict(list)
        for l_id, lap in enumerate(self.lap_list):

            rows = lap.row
            cols = lap.col

            for i_id in range(len(rows)):
                head = rows[i_id]
                tail = cols[i_id]
                relation = self.adj_r_list[l_id]
                all_item_dict[head].append((tail, relation))
        return all_item_dict

    def _get_all_item_data(self):
        def _reorder_list(org_list, order):
            new_list = np.array(org_list)
            new_list = new_list[order]
            return new_list

        all_h_list, all_t_list, all_r_list = [], [], []
        all_v_list = []

        for l_id, lap in enumerate(self.lap_list):
            all_h_list += list(lap.row)
            all_t_list += list(lap.col)
            all_v_list += list(lap.data)
            all_r_list += [self.adj_r_list[l_id]] * len(lap.row)

        assert len(all_h_list) == sum([len(lap.data) for lap in self.lap_list])

        org_h_dict = dict()

        for idx, h in enumerate(all_h_list):
            if h not in org_h_dict.keys():
                org_h_dict[h] = [[],[],[]]
            org_h_dict[h][0].append(all_t_list[idx])
            org_h_dict[h][1].append(all_r_list[idx])
            org_h_dict[h][2].append(all_v_list[idx])
       
        sorted_h_dict = dict()
        for h in org_h_dict.keys():
            org_t_list, org_r_list, org_v_list = org_h_dict[h]
            sort_t_list = np.array(org_t_list)
            sort_order = np.argsort(sort_t_list)

            sort_t_list = _reorder_list(org_t_list, sort_order)
            sort_r_list = _reorder_list(org_r_list, sort_order)
            sort_v_list = _reorder_list(org_v_list, sort_order)
            sorted_h_dict[h] = [sort_t_list, sort_r_list, sort_v_list]


        od = collections.OrderedDict(sorted(sorted_h_dict.items()))
        new_h_list, new_t_list, new_r_list, new_v_list = [], [], [], []

        for h, vals in od.items():
            new_h_list += [h] * len(vals[0])
            new_t_list += list(vals[0])
            new_r_list += list(vals[1])
            new_v_list += list(vals[2])
        assert sum(new_h_list) == sum(all_h_list)
        assert sum(new_t_list) == sum(all_t_list)
        assert sum(new_r_list) == sum(all_r_list)



        return new_h_list, new_r_list, new_t_list, new_v_list

   


    def _generate_train_A_batch(self):
        exist_heads = self.all_item_dict.keys()

        if self.batch_size_item <= len(exist_heads):
            heads = rd.sample(exist_heads, self.batch_size_item)
        else:
            heads = [rd.choice(exist_heads) for _ in range(self.batch_size_item)]

        def sample_pos_triples_for_h(h, num):
            pos_triples = self.all_item_dict[h]
            n_pos_triples = len(pos_triples)

            pos_rs, pos_ts = [], []
            while True:
                if len(pos_rs) == num: break
                pos_id = np.random.randint(low=0, high=n_pos_triples, size=1)[0]

                t = pos_triples[pos_id][0]
                r = pos_triples[pos_id][1]

                if r not in pos_rs and t not in pos_ts:
                    pos_rs.append(r)
                    pos_ts.append(t)
            return pos_rs, pos_ts

        def sample_neg_triples_for_h(h, r, num):
            neg_ts = []
            while True:
                if len(neg_ts) == num: break

                t = np.random.randint(low=0, high=self.n_users + self.n_entities, size=1)[0]
                if (t, r) not in self.all_item_dict[h] and t not in neg_ts:
                    neg_ts.append(t)
            return neg_ts

        pos_r_batch, pos_t_batch, neg_t_batch = [], [], []

        for h in heads:
            pos_rs, pos_ts = sample_pos_triples_for_h(h, 1)
            pos_r_batch += pos_rs
            pos_t_batch += pos_ts

            neg_ts = sample_neg_triples_for_h(h, pos_rs[0], 1)
            neg_t_batch += neg_ts

        return heads, pos_r_batch, pos_t_batch, neg_t_batch
    def generate_train_batch(self):
        users, pos_items, neg_items = self._generate_train_cf_batch()

        batch_data = {}
        batch_data['users'] = users
        batch_data['pos_items'] = pos_items
        batch_data['neg_items'] = neg_items

        return batch_data

    def generate_train_feed_dict(self, model, batch_data):
        feed_dict = {
            model.users: batch_data['users'],
            model.pos_items: batch_data['pos_items'],
            model.neg_items: batch_data['neg_items'],

            model.mess_dropout: eval(self.args.mess_dropout),
            model.node_dropout: eval(self.args.node_dropout),
        }

        return feed_dict

    def generate_train_A_batch(self):
        heads, relations, pos_tails, neg_tails = self._generate_train_A_batch()

        batch_data = {}

        batch_data['heads'] = heads
        batch_data['relations'] = relations
        batch_data['pos_tails'] = pos_tails
        batch_data['neg_tails'] = neg_tails
        return batch_data

    def generate_train_A_feed_dict(self, model, batch_data):
        feed_dict = {
            model.h: batch_data['heads'],
            model.r: batch_data['relations'],
            model.pos_t: batch_data['pos_tails'],
            model.neg_t: batch_data['neg_tails'],

        }

        return feed_dict
    def generate_train_A_feed_dict_group(self, model, batch_data):
        feed_dict = {
            model.h_group: batch_data['heads'],
            model.r_group: batch_data['relations'],
            model.pos_t_group: batch_data['pos_tails'],
            model.neg_t_group: batch_data['neg_tails'],

        }

        return feed_dict

    def generate_test_feed_dict(self, model, user_batch, item_batch, drop_flag=True):

        feed_dict ={
            model.users: user_batch,
            model.pos_items: item_batch,
            model.mess_dropout: [0.] * len(eval(self.args.layer_size)),
            model.node_dropout: [0.] * len(eval(self.args.layer_size)),

        }

        return feed_dict

