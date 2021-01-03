# -*- coding: utf-8 -*-
"""
@author: hanfeng.lin
@contact: wahaha
@Created on: 2020/12/25 15:15
"""
from django.core.files.storage import Storage
from fdfs_client.client import get_tracker_conf, Fdfs_client

from dailyfresh.settings import FDFS_NGINX_URL, FDFS_CLIENT_CONF


class FDFSStorage(Storage):

    def __init__(self, fdfs_conf=None, nginx_url=None):
        '''
        可自由配置
        :param fdfs_conf:  fdsf配置文件地址
        :param nginx_url:  nginx的url地址
        '''
        self.fdfs_conf = FDFS_CLIENT_CONF if fdfs_conf is None else fdfs_conf
        self.nginx_url = FDFS_NGINX_URL if nginx_url is None else nginx_url

    def _open(self, name, mode='rb'):
        '''
        打开文件
        :param name:
        :param mode:
        :return:
        '''
        pass

    def _save(self, name, content):
        '''
        文件上传
        :param name:  上传文件名称
        :param content:  上传文件内容 File 对象自身
        :return: 上传成功文件名
        '''
        # 实例化对象
        trackers = get_tracker_conf(self.fdfs_conf)
        client = Fdfs_client(trackers)
        # 使用上传内容方法
        res = client.upload_appender_by_buffer(content.read())

        # @return dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }
        # 文件上传失败
        if res.get('Status') != 'Upload successed.':
            # 谁调用谁出来异常
            raise Exception('文件上传失败！')
        name = res.get('Remote file_id')
        # 不编码会报错
        return name.decode()

    def exists(self, name):
        '''
        判断文件是否存在
        :param name:
        :return:
        '''
        return False

    def url(self, name):
        '''
        文件访问的地址
        :param name:
        :return:
        '''
        return self.nginx_url + name
