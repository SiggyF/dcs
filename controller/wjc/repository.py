import json
from logging.config import dictConfig
import pickle
import logging
import shutil
import uuid
import redis
from job_midwife import JobMidwife
from job import Job
from batch import Batch

with open('logging.json') as jl:
    dictConfig(json.load(jl))

class JobRepository:
    def __init__(self):
        try:
            self.client = redis.Redis('db')
            self.midwife = JobMidwife(self.client)
            self.midwife.start()
        except Exception, e:
            logging.exception('Something is fishy (%s)' % e)

    def get_all_jobs(self):
        result = []
        for job_key in self.client.keys('job-*'):
            job = pickle.loads(self.client.get(job_key))
            result.append([job_key, job.state, job.ami, job.instance_type])
        return result

    def get_job_state(self, job_id):
        if job_id.startswith('job-'):
            if self.client.exists(job_id):
                job = pickle.loads(self.client.get(job_id))
                if job is not None:
                    return job.state
                return 'job not found'
        return 'not a job'

    def set_job_state(self, job_id, state):
        if job_id.startswith('job-'):
            if self.client.exists(job_id):
                job = pickle.loads(self.client.get(job_id))
                if job is not None:
                    job.state = state
                    self.client.set(job_id, pickle.dumps(job))
                    self.client.publish('jobs', job_id)
                    return 'ok'
                return 'job not found'
        return 'not a job'

    def get_all_batch(self):
        result = []
        for batch_key in self.client.keys('batch-*'):
            batch = pickle.loads(self.client.get(batch_key))
            result.append([batch_key, batch.state, batch.ami, batch.instance_type, batch.max_nodes, batch.jobs])
        return result

    def execute_batch(self, max_nodes, ami, instance_type):
        batch_id = 'batch-%s' % uuid.uuid4()
        batch = Batch('received')
        batch.ami = ami
        batch.instance_type = instance_type
        batch.max_nodes = max_nodes
        self.client.set(batch_id, pickle.dumps(batch))
        return batch_id

    def delete_batch(self, batch_id):
        if batch_id.startswith('batch-'):
            if self.client.exists(batch_id):
                batch = pickle.loads(self.client.get(batch_id))
                for job_id in batch.jobs:
                    if self.client.exists(job_id):
                        self.client.remove(job_id)
                        self.client.publish('jobs', job_id)
                try:
                    shutil.rmtree('/tmp/store/%s' % batch_id)
                except Exception, e:
                    raise 'could not delete %s (%s)' % (batch_id, e)
                finally:
                    result = self.client.delete(batch_id)
                    return result
        return 'not a batch'

    def get_batch_state(self, batch_id):
        if batch_id.startswith('batch-'):
            if self.client.exists(batch_id):
                batch = pickle.loads(self.client.get(batch_id))
                if batch is not None:
                    return batch.state
                return 'batch not found'
        return 'not a batch'

    def set_batch_state(self, batch_id, state):
        if batch_id.startswith('batch-'):
            if self.client.exists(batch_id):
                batch = pickle.loads(self.client.get(batch_id))
                batch.state = state
                self.client.set(batch_id, pickle.dumps(batch))
                return 'ok'
        return 'not a batch'
