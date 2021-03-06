# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
# Copyright (C) 2014 The Trustees of Indiana University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time
import ipaddr
import pprint
import libxml2
from SimpleBalancer import SimpleBalancer

class SciPass:
  """SciPass API for signaling when a flow is known good or bad"""
  def __init__(  self , *_args, **_kwargs):
    self.logger = None
    self.configFile = None
    if(_kwargs.has_key('logger')):
      self.logger = _kwargs['logger']

    if(self.logger == None):
      logging.basicConfig()
      self.logger = logging.getLogger(__name__)


    if(_kwargs.has_key('config')):
      self.configFile = _kwargs['config']
    else:
      self.configFile = "/etc/SciPass/SciPass.xml"


    self.whiteList    = []
    self.blackList    = []
    self.idleTimeouts = []
    self.hardTimeouts = []
    self.switches     = []
    self.switchForwardingChangeHandlers = []
    self._processConfig(self.configFile)

  def registerForwardingStateChangeHandler(self, handler):
    self.switchForwardingChangeHandlers.append(handler)

  def good_flow(self, obj):
    #turn this into a 
    #presumes that we get a nw_src, nw_dst, tcp_src_port, tcp_dst_port
    #we need to do verification here or conversion depending on what we get from the sensors
    in_port = None
    out_port = None
    dpid = None
    domain = None
    reverse = False
    new_prefix = ipaddr.IPv4Network(obj['nw_src'])

    #need to figure out the lan and wan ports
    for datapath_id in self.config:
      for name in self.config[datapath_id]:
        for port in self.config[datapath_id][name]['ports']['lan']:
            for prefix in port['prefixes']:
              self.logger.error("Comparing" + str(new_prefix) + " " + str(prefix['prefix']))
              if(prefix['prefix'].Contains( new_prefix )):
                in_port = port
                dpid = datapath_id
                domain = name
                
    if(in_port == None):
      new_prefix = ipaddr.IPv4Network(obj['nw_dst'])
      #do the same but look for the dst instead of the src
      for datapath_id in self.config:
        for name in self.config[datapath_id]:
          for port in self.config[datapath_id][name]['ports']['lan']:
            for prefix in port['prefixes']:
              if(prefix['prefix'].Contains( new_prefix )):
                in_port = port
                dpid = datapath_id
                domain = name
                reverse = True

    if(in_port == None):
      self.logger.error("unable to find either an output or an input port")
      return

    obj['phys_port'] = int(in_port['port_id'])

    actions = [{"type": "output", 
                "port": self.config[dpid][name]['ports']['wan'][0]['port_id']}]

    idle_timeout = None
    priority     = self.config[dpid][name]['default_whitelist_priority']
    self.logger.debug("Idle Timeout: " + self.config[dpid][name]['idle_timeout'])
    self.logger.debug("Priority: " + priority)
    
    header = {}
    if(not obj.has_key('idle_timeout')):
      idle_timeout  = self.config[dpid][name]['idle_timeout']
    else:
      idle_timeout = obj['idle_timeout']
      
    self.logger.debug("Selected Idle Timeout: " + str(idle_timeout))

    if(not obj.has_key('priority')):
      priority = self.config[dpid][name]['default_whitelist_priority']
    else:
      priority = obj['priority']

    if(obj.has_key('nw_src')):
      if(reverse):
        prefix = ipaddr.IPv4Network(obj['nw_src'])
        header['nw_dst'] = int(prefix)
        header['nw_dst_mask'] = int(prefix.prefixlen)
      else:
        prefix = ipaddr.IPv4Network(obj['nw_src'])
        header['nw_src'] = int(prefix)
        header['nw_src_mask'] = int(prefix.prefixlen)

    if(obj.has_key('nw_dst')):
      if(reverse):
        prefix = ipaddr.IPv4Network(obj['nw_dst'])
        header['nw_src'] = int(prefix)
        header['nw_src_mask'] = int(prefix.prefixlen)
      else:
        prefix = ipaddr.IPv4Network(obj['nw_dst'])
        header['nw_dst'] = int(prefix)
        header['nw_dst_mask'] = int(prefix.prefixlen)

    if(obj.has_key('tp_src')):
      if(reverse):
        header['tp_dst'] = int(obj['tp_src'])
      else:
        header['tp_src'] = int(obj['tp_src'])

    if(obj.has_key('tp_dst')):
      if(reverse):
        header['tp_src'] = int(obj['tp_dst'])
      else:
        header['tp_dst'] = int(obj['tp_dst'])

    header['phys_port'] = int(in_port['port_id'])

    self.logger.debug("Header: " + str(header))

    

    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            domain       = domain,
                                            header       = header,
                                            actions      = actions,
                                            command      = "ADD",
                                            idle_timeout = idle_timeout,
                                            hard_timeout = 0,
                                            priority     = priority)
      

    header = {}
    if(not obj.has_key('idle_timeout')):
      idle_timeout  = self.config[dpid][name]['idle_timeout']
    else:
      idle_timeout = obj['idle_timeout']

    self.logger.debug("Selected Idle Timeout: " + str(idle_timeout))

    if(not obj.has_key('priority')):
      priority = self.config[dpid][name]['default_whitelist_priority']
    else:
      priority = obj['priority']

    if(obj.has_key('nw_src')):
      if(reverse):
        prefix = ipaddr.IPv4Network(obj['nw_src'])
        header['nw_src'] = int(prefix)
        header['nw_src_mask'] = int(prefix.prefixlen)
      else:
        prefix = ipaddr.IPv4Network(obj['nw_src'])
        header['nw_dst'] = int(prefix)
        header['nw_dst_mask'] = int(prefix.prefixlen)
    if(obj.has_key('nw_dst')):
      if(reverse):
        prefix = ipaddr.IPv4Network(obj['nw_dst'])
        header['nw_dst'] = int(prefix)
        header['nw_dst_mask'] = int(prefix.prefixlen)
      else:
        prefix = ipaddr.IPv4Network(obj['nw_dst'])
        header['nw_src'] = int(prefix)
        header['nw_src_mask'] = int(prefix.prefixlen)

    if(obj.has_key('tp_src')):
      if(reverse):
        header['tp_src'] = int(obj['tp_src'])
      else:
        header['tp_dst'] = int(obj['tp_src'])

    if(obj.has_key('tp_dst')):
      if(reverse):
        header['tp_dst'] = int(obj['tp_dst'])
      else:
        header['tp_src'] = int(obj['tp_dst'])

    header['phys_port'] = int(self.config[dpid][name]['ports']['wan'][0]['port_id'])
    
    actions = [{"type": "output",
                "port": in_port['port_id']}]
    
    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            domain       = domain,
                                            header       = header,
                                            actions      = actions,
                                            command      = "ADD",
                                            idle_timeout = idle_timeout,
                                            hard_timeout = 0,
                                            priority     = priority)
    
    results = {}
    results['success'] = 1
    return results

  def bad_flow(self, obj):
    #turn this into a
    #presumes that we get a nw_src, nw_dst, tcp_src_port, tcp_dst_port
    #we need to do verification here or conversion depending on what we get from the sensors
    in_port = None
    out_port = None
    dpid = None
    domain = None
    reverse = False

    new_prefix = ipaddr.IPv4Network(obj['nw_src'])
    self.logger.debug("New preifx: " + str(new_prefix))
    #need to figure out the lan and wan ports
    for datapath_id in self.config:
      for name in self.config[datapath_id]:
        for port in self.config[datapath_id][name]['ports']['lan']:
            for prefix in port['prefixes']:
              if(prefix['prefix'].Contains( new_prefix )):
                in_port = port
                dpid = datapath_id
                domain = name

    if(in_port == None):
      new_prefix = ipaddr.IPv4Network(obj['nw_dst'])
      #do the same but look for the dst instead of the src                                                             
      for datapath_id in self.config:
        for name in self.config[datapath_id]:
          for port in self.config[datapath_id][name]['ports']['lan']:
            for prefix in port['prefixes']:
              if(prefix['prefix'].Contains( new_prefix )):
                in_port = port
                dpid = datapath_id
                domain = name
                reverse = True

    if(in_port == None):
      self.logger.debug("unable to find either an output or an input port")
      return

    obj['phys_port'] = int(in_port['port_id'])

    #actions = drop
    actions = []

    idle_timeout = None
    hard_timeout = None
    priority     = self.config[dpid][name]['default_blacklist_priority']

    header = {}
    if(not obj.has_key('idle_timeout')):
      idle_timeout  = self.config[dpid][name]['idle_timeout']
    else:
      idle_timeout = obj['idle_timeout']

    self.logger.debug("Selected Idle Timeout: " + str(idle_timeout))

    if(not obj.has_key('priority')):
      priority = self.config[dpid][name]['default_whitelist_priority']
    else:
      priority = obj['priority']

    if(obj.has_key('nw_src')):
      if(reverse):
        prefix = ipaddr.IPv4Network(obj['nw_src'])
        header['nw_dst'] = int(prefix)
        header['nw_dst_mask'] = int(prefix.prefixlen)
      else:
        prefix = ipaddr.IPv4Network(obj['nw_src'])
        header['nw_src'] = int(prefix)
        header['nw_src_mask'] = int(prefix.prefixlen)
    if(obj.has_key('nw_dst')):
      if(reverse):
        prefix = ipaddr.IPv4Network(obj['nw_dst'])
        header['nw_src'] = int(prefix)
        header['nw_src_mask'] = int(prefix.prefixlen)
      else:
        prefix = ipaddr.IPv4Network(obj['nw_dst'])
        header['nw_dst'] = int(prefix)
        header['nw_dst_mask'] = int(prefix.prefixlen)

    if(obj.has_key('tp_src')):
      if(reverse):
        header['tp_dst'] = int(obj['tp_src'])
      else:
        header['tp_src'] = int(obj['tp_src'])

    if(obj.has_key('tp_dst')):
      if(reverse):
        header['tp_src'] = int(obj['tp_dst'])
      else:
        header['tp_dst'] = int(obj['tp_dst'])

    header['phys_port'] = int(in_port['port_id'])

    self.logger.debug("Header: " + str(header))

    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            domain       = domain,
                                            header       = header,
                                            actions      = actions,
                                            command      = "ADD",
                                            idle_timeout = idle_timeout,
                                            priority     = priority)

    header = {}
    if(not obj.has_key('idle_timeout')):
      idle_timeout  = self.config[dpid][name]['idle_timeout']
    else:
      idle_timeout = obj['idle_timeout']

    self.logger.debug("Selected Idle Timeout: " + str(idle_timeout))

    if(not obj.has_key('priority')):
      priority = self.config[dpid][name]['default_whitelist_priority']
    else:
      priority = obj['priority']

    if(obj.has_key('nw_src')):
      if(reverse):
        prefix = ipaddr.IPv4Network(obj['nw_src'])
        header['nw_src'] = int(prefix)
        header['nw_src_mask'] = int(prefix.prefixlen)
      else:
        prefix = ipaddr.IPv4Network(obj['nw_src'])
        header['nw_dst'] = int(prefix)
        header['nw_dst_mask'] = int(prefix.prefixlen)
    if(obj.has_key('nw_dst')):
      if(reverse):
        prefix = ipaddr.IPv4Network(obj['nw_dst'])
        header['nw_dst'] = int(prefix)
        header['nw_dst_mask'] = int(prefix.prefixlen)
      else:
        prefix = ipaddr.IPv4Network(obj['nw_dst'])
        header['nw_src'] = int(prefix)
        header['nw_src_mask'] = int(prefix.prefixlen)
    if(obj.has_key('tp_src')):
      if(reverse):
        header['tp_src'] = int(obj['tp_src'])
      else:
        header['tp_dst'] = int(obj['tp_src'])

    if(obj.has_key('tp_dst')):
      if(reverse):
        header['tp_dst'] = int(obj['tp_dst'])
      else:
        header['tp_src'] = int(obj['tp_dst'])

    header['phys_port'] = int(self.config[dpid][name]['ports']['wan'][0]['port_id'])

    #actions = drop
    actions = []

    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            domain       = domain,
                                            header       = header,
                                            actions      = actions,
                                            command      = "ADD",
                                            idle_timeout = idle_timeout,
                                            hard_timeout = 0,
                                            priority     = priority)


    results = {}
    results['success'] = 1
    return results

  def get_bad_flow(self):
    return self.whiteList

  def get_good_flow(self):
    return self.blackList

  # gets the config info for a sensor along with its dpid and domain
  def _getSensorInfo(self, port_id):
    # loop through dpids
    for dpid in self.config:
      # loop through domains
      for domain_name in self.config[dpid]:
          domain = self.config[dpid][domain_name]
          # loop through sensors
          for group in domain.get('sensor_port_groups'):
            sensors = domain.get('sensor_port_groups')[group];
            for sensor in sensors:
              # return sensor info if we've found our port
              if(str(sensor.get('of_port_id')) == str(port_id)):
                return {
                  'dpid':   dpid,
                  'domain': domain_name,
                  'group': group,
                  'sensor_info': sensor
                }

  def setSensorStatus(self, port_id, status):
    info = self._getSensorInfo(port_id) 
    if(info == None): return
    # set sensor status 
    self.config[info.get('dpid')][info.get('domain')]['balancer'].setSensorStatus(
        info['sensor_info'].get('sensor_id'), 
        status
    )

  def _processConfig(self, xmlFile):
    self.logger.debug("Processing Config file")
    doc = libxml2.parseFile(xmlFile)
    ctxt = doc.xpathNewContext()
    #parse the xml file
    switches = ctxt.xpathEval("//SciPass/switch")
    config = {}
    for switch in switches:
      ctxt.setContextNode(switch)
      dpid = switch.prop("dpid")
      self.logger.debug("Switch DPID: " + str(dpid))
      config[dpid] = {}
      domains = ctxt.xpathEval("domain")
      for domain in domains:
        ctxt.setContextNode(domain)
        name = domain.prop("name")
        mode = domain.prop("mode")
        status = domain.prop("admin_status")
        max_prefixes = domain.prop("max_prefixes")
        most_specific_len = domain.prop("most_specific_prefix_len")
        least_specific_len = domain.prop("least_specific_prefix_len")
        idle_timeout = domain.prop("idle_timeout")
        hard_timeout = domain.prop("hard_timeout")
        default_blacklist_priority = domain.prop("blacklist_priority")
        default_whitelist_priority = domain.prop("whitelist_priority")
        sensorLoadMinThreshold = domain.prop("sensor_min_load_threshold")
        sensorLoadDeltaThreshhold = domain.prop("sensor_load_delta_threshold")
        ignore_sensor_load = domain.prop("ignore_sensor_load")
        ignore_prefix_bw = domain.prop("ignore_prefix_bw")
        self.logger.debug("Adding Domain: name: %s, mode: %s, status: %s", name, mode, status)

        config[dpid][name] = {}
        config[dpid][name]['mode'] = mode
        config[dpid][name]['status'] = status
        config[dpid][name]['max_prefixes'] = max_prefixes
        config[dpid][name]['most_specific_prefix_len'] = most_specific_len
        config[dpid][name]['least_specific_prefix_len'] = least_specific_len
        config[dpid][name]['idle_timeout'] = idle_timeout
        config[dpid][name]['hard_timeout'] = hard_timeout
        config[dpid][name]['default_blacklist_priority'] = default_blacklist_priority
        config[dpid][name]['default_whitelist_priority'] = default_whitelist_priority
        config[dpid][name]['sensor_load_min_threshold'] = sensorLoadMinThreshold
        config[dpid][name]['sensor_load_delta_threshold'] = sensorLoadDeltaThreshhold

        if(ignore_prefix_bw == "true"):
          config[dpid][name]['ignore_prefix_bw'] = 1
        else:
          config[dpid][name]['ignore_prefix_bw'] = 0

        if(ignore_sensor_load == "true"):
          config[dpid][name]['ignore_sensor_load'] = 1
        else:
          config[dpid][name]['ignore_sensor_load'] = 0

        config[dpid][name]['sensor_groups'] = {}
        config[dpid][name]['ports'] = {}
        config[dpid][name]['ports']['lan'] = []
        config[dpid][name]['ports']['wan'] = []
        config[dpid][name]['ports']['fw_lan'] = []
        config[dpid][name]['ports']['fw_wan'] = []
        #create a simple balancer
        config[dpid][name]['balancer'] = SimpleBalancer( logger = self.logger,
                                                         maxPrefixes = max_prefixes,
                                                         ignoreSensorLoad = config[dpid][name]['ignore_sensor_load'],
                                                         ignorePrefixBW = config[dpid][name]['ignore_prefix_bw'],
                                                         mostSpecificPrefixLen = most_specific_len,
                                                         sensorLoadMinThresh = sensorLoadMinThreshold,
                                                         sensorLoadDeltaThresh = sensorLoadDeltaThreshhold,
                                                         leastSpecificPrefixLen = least_specific_len
                                                         ) 
        config[dpid][name]['flows'] = []
        #register the methods
        config[dpid][name]['balancer'].registerAddPrefixHandler(lambda x, y : self.addPrefix(dpid = dpid,
                                                                                            domain_name = name,
                                                                                            group_id = x,
                                                                                            prefix = y))

        config[dpid][name]['balancer'].registerDelPrefixHandler(lambda x, y : self.delPrefix(dpid = dpid,
                                                                                            domain_name = name,
                                                                                            group_id = x,
                                                                                            prefix = y))

        config[dpid][name]['balancer'].registerMovePrefixHandler(lambda x, y, z : self.movePrefix(dpid = dpid,
                                                                                              domain_name = name,
                                                                                              old_group_id = x,
                                                                                              new_group_id = y,
                                                                                              prefix = z
                                                                                              ))

        ports = ctxt.xpathEval("port")
        sensor_groups = ctxt.xpathEval("sensor_group")
        for port in ports:
          ctxt.setContextNode(port)
          ptype = port.prop("type")
          vlan_tag = port.prop("vlan_tag")
          prefixes = ctxt.xpathEval("prefix")
          prefixes_array = []
          for prefix in prefixes:
            prefix_obj = {}
            if(prefix.prop("type") == "v4" or prefix.prop("type") == "ipv4"):
              prefix_obj = {"type": prefix.prop("type"),
                            "prefix_str": prefix.getContent(),
                            "prefix": ipaddr.IPv4Network(prefix.getContent())}
            else:
              #eventually we'll be able to do this, but for now
              #we are going to hardcode ::/128 so that its considered a single 
              #prefix that is not divisible anymore
              prefix_obj = {"type": prefix.prop("type"),
                            "prefix_str": "::/128", #prefix.getContent(),
                            "prefix": ipaddr.IPv6Network(prefix.getContent())}
                            
            prefixes_array.append(prefix_obj)

          config[dpid][name]['ports'][ptype].append({"port_id": port.prop("of_port_id"),
                                                     "name": port.prop("name"),
                                                     "description": port.prop("description"),
                                                     "prefixes": prefixes_array,
                                                     "vlan_tag": vlan_tag
                                                     })
          
        for group in sensor_groups:
          ctxt.setContextNode(group)
          group_info = {"bw": group.prop("bw"),
                        "group_id": group.prop("group_id"),
                        "admin_state": group.prop("admin_state"),
                        "description": group.prop("description"),
                        "sensors": {}}
          config[dpid][name]['sensor_groups'][group.prop("group_id")] = group_info
          sensors = ctxt.xpathEval("sensor")
          for sensor in sensors:
            sensor = {"port_id": sensor.prop("of_port_id"),
                      "sensor_id": sensor.prop("sensor_id")}
            config[dpid][name]['sensor_groups'][group_info['group_id']]['sensors'][sensor['sensor_id']] = sensor
          config[dpid][name]['balancer'].addSensorGroup(group_info)
        
    self.config = config      
    doc.freeDoc()
    ctxt.xpathFreeContext()

  def switchJoined(self, datapath):
    #check to see if we are suppose to operate on this switch
    self.switches.append(datapath)
    dpid = "%016x" % datapath.id
    if(self.config.has_key(dpid)):
      self.logger.info("Switch has joined!")
      #now for each domain push the initial flows 
      #and start the balancing process
      for domain_name in self.config[dpid]:
        domain = self.config[dpid][domain_name]
        if(domain['mode'] == "SciDMZ"):
          #we have firewals configured
          #setup the rules to them
          self.logger.info("Mode is Science DMZ")
          #need to install the default rules forwarding everything through the FW
          #then install the balancing rules for our defined prefixes
          self._setupSciDMZRules(dpid = dpid,
                                 domain_name = domain_name)

        elif(domain['mode'] == "InlineIDS"):
          #no firewall
          self.logger.info("Mode is Inline IDS")
          #need to install the default rules forwarding through the switch
          #then install the balancing rules for our defined prefixes
          self._setupInlineIDS(dpid = dpid, domain_name = domain_name)
        elif(domain['mode'] == "Balancer"):
          #just balancer no other forwarding
          self.logger.info("Mode is Balancer")
          #just install the balance rules, no forwarding
          self._setupBalancer(dpid = dpid, domain_name = domain_name)
        
          
  def _setupSciDMZRules(self, dpid = None, domain_name = None):
    self.logger.debug("SciDMZ rule init")
    #just in and out port rules for the 
    #NOTE this presumes many input and 1 output port total and 1 fw lan/wan port for each domain

    #lowest priority
    priority = 10
    prefixes = []
    ports = self.config[dpid][domain_name]['ports']

    if(len(ports['fw_wan']) <= 0 or len(ports['fw_lan']) <= 0):
      #well crap no fw_wan or fw_lan exist... what are bypassing?
      self.logger.warn("nothing to bypass.. you probably want InlineIDS mode... doing that instead")
      self._setupInlineIDS(dpid = dpid, domain_name = domain_name)
      return

    fw_lan_outputs = []

    for in_port in ports['lan']:
      header = {"phys_port":   int(in_port['port_id']),
                'dl_type': None}

      actions = []
      #output to FW
      actions.append({"type": "output",
                      "port": int(ports['fw_lan'][0]['port_id'])})

      fw_lan_outputs.append({"type": "output",
                             "port": int(in_port['port_id'])})

      self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                              domain     = domain_name,
                                              header       = header,
                                              actions      = actions,
                                              command      = "ADD",
                                              idle_timeout = 0,
                                              hard_timeout = 0,
                                              priority     = int(priority / 2))

      for prefix in in_port['prefixes']:
        prefixes.append(prefix['prefix'])
        #specific prefix forwarding rules
        #FW LAN to specific LAN PORT
        header = {}
        if(prefix['type'] != "v4" and prefix['type'] != "ipv4"):
          header = {"dl_type": 34525,
                    "phys_port": int(ports['fw_lan'][0]['port_id'])}
        else:
          header = {"phys_port": int(ports['fw_lan'][0]['port_id']),
                    "nw_dst": int(prefix['prefix']),
                    "nw_dst_mask": int(prefix['prefix'].prefixlen)}
        
        actions = []
        actions.append({"type": "output",
                        "port": int(in_port['port_id'])})
        
        self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                                domain     = domain_name,
                                                header       = header,
                                                actions      = actions,
                                                command      = "ADD",
                                                idle_timeout = 0,
                                                hard_timeout = 0,
                                                priority     = int(priority))
        
        #SPECIFIC LAN -> FW LAN port
        header = {}
        if(prefix['type'] != "v4" and prefix['type'] != "ipv4"):
          header = {"dl_type": 34525,
                    "phys_port": int(in_port['port_id'])}
        else:
          header = {"phys_port": int(in_port['port_id']),
                    "nw_src": int(prefix['prefix']),
                    "nw_src_mask": int(prefix['prefix'].prefixlen)}

        actions = []
        actions.append({"type": "output",
                        "port": int(ports['fw_lan'][0]['port_id'])})

        self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                                domain       = domain_name,
                                                header       = header,
                                                actions      = actions,
                                                command      = "ADD",
                                                idle_timeout = 0,
                                                hard_timeout = 0,
                                                priority     = int(priority))

    #FW LAN to ALL INPUT PORTS
    header = {"phys_port": int(ports['fw_lan'][0]['port_id']),
              'dl_type': None}
    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            domain       = domain_name,
                                            header       = header,
                                            actions      = fw_lan_outputs,
                                            command      = "ADD",
                                            idle_timeout = 0,
                                            hard_timeout = 0,
                                            priority     = int(priority / 3))

    #FW WAN -> WAN
    header = {"phys_port": int(ports['fw_wan'][0]['port_id']),
              'dl_type': None}
    actions = []
    actions.append({"type": "output",
                    "port": int(ports['wan'][0]['port_id'])})
    self.logger.error("FW WAN -> WAN: ")
    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            domain       = domain_name,
                                            header       = header,
                                            actions      = actions,
                                            command      = "ADD",
                                            idle_timeout = 0,
                                            hard_timeout = 0,
                                            priority     = int(priority))

    #WAN -> FW WAN
    header = {"phys_port": int(ports['wan'][0]['port_id']),
              'dl_type': None}
    actions = []
    actions.append({"type": "output",
                    "port": int(ports['fw_wan'][0]['port_id'])})
    self.logger.error("WAN -> FW WAN")
    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            domain       = domain_name,
                                            header       = header,
                                            actions      = actions,
                                            command      = "ADD",
                                            idle_timeout = 0,
                                            hard_timeout = 0,
                                            priority     = int(priority))

    #ok now that we have that done... start balancing!!!
    self.config[dpid][domain_name]['balancer'].distributePrefixes(prefixes)
    

  def _setupInlineIDS(self, dpid = None, domain_name = None):
    self.logger.debug("InLine IDS rule init")
    #no firewall
    #basically distribute prefixes and setup master forwarding
    priority = 10
    prefixes = []
    ports = self.config[dpid][domain_name]['ports']

    in_port = ports['lan'][0]

    for prefix in in_port['prefixes']:
      prefixes.append(prefix['prefix'])

    #LAN to WAN
    header = {"phys_port": int(ports['lan'][0]['port_id']),
              'dl_type': None}
        
    actions = []
    actions.append({'type':'output',
                    'port':int(ports['wan'][0]['port_id'])})
    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            header       = header,
                                            domain       = domain_name,
                                            actions      = actions,
                                            command      = "ADD",
                                            idle_timeout = 0,
                                            hard_timeout = 0,
                                            priority     = int(priority / 3))

    #WAN -> LAN
    header = {"phys_port": int(ports['wan'][0]['port_id']),
              'dl_type': None}
    actions = []
    actions.append({"type": "output",
                    "port": int(ports['lan'][0]['port_id'])})
    self.logger.error("FW WAN -> WAN: ")
    self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                            domain       = domain_name,
                                            header       = header,
                                            actions      = actions,
                                            command      = "ADD",
                                            idle_timeout = 0,
                                            hard_timeout = 0,
                                            priority     = int(priority / 3))

    #ok now that we have that done... start balancing!!!
    self.config[dpid][domain_name]['balancer'].distributePrefixes(prefixes)

  def _setupBalancer(self, dpid = None, domain_name = None):
    self.logger.debug("balancer rule init")
    #ok now that we have that done... start balancing!!!
    prefixes = []
    ports = self.config[dpid][domain_name]['ports']
    for port in ports['lan']:
      in_port = port
      for prefix in in_port['prefixes']:
        prefixes.append(prefix['prefix'])

    self.config[dpid][domain_name]['balancer'].distributePrefixes(set(prefixes))
        
  def addPrefix(self, dpid=None, domain_name=None, group_id=None, prefix=None):
    #self.logger.error("Add Prefix " + str(domain_name) + " " + str(group_id) + " " + str(prefix))
    #find the north and south port

    in_port  = None
    out_port = None
    fw_lan   = None
    fw_wan   = None
    #need to figure out the lan and wan ports

    ports = self.config[dpid][domain_name]['ports']

    for port in ports['lan']:
      for prefix_obj in port['prefixes']:
        if(prefix_obj['prefix'].Contains( prefix )):
          #self.logger.error("Prefix: " + str(prefix_obj['prefix']) + " contains " + str(prefix)) 
          in_port = port
         
          header = {}
          if(prefix._version != 4):
            header = {"dl_type": 34525,
                      "phys_port": int(in_port['port_id'])}
          else:
            header = {"nw_src":      int(prefix),
                      "nw_src_mask": int(prefix.prefixlen),
                      "phys_port":   int(in_port['port_id'])}

          actions = []
          #output to sensor (basically this is the IDS balance case)
          sensors = self.config[dpid][domain_name]['sensor_groups'][group_id]['sensors']
          for sensor in sensors:
            self.logger.debug("output: " + str(sensors[sensor]));
            actions.append({"type": "output",
                            "port": sensors[sensor]['port_id']})
          
          if(self.config[dpid][domain_name]['mode'] == "SciDMZ" or self.config[dpid][domain_name]['mode'] == "InlineIDS"):
          #append the FW or other destination
            if(ports.has_key('fw_lan') and len(ports['fw_lan']) > 0):
              actions.append({"type": "output",
                              "port": ports['fw_lan'][0]['port_id']})
            else:
              actions.append({"type": "output",
                              "port": ports['wan'][0]['port_id']})

          self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                                  domain       = domain_name,
                                                  header       = header,
                                                  actions      = actions,
                                                  command      = "ADD",
                                                  idle_timeout = 0,
                                                  hard_timeout = 0,
                                                  priority     = 500)

          header = {}
          if(self.config[dpid][domain_name]['mode'] == "SciDMZ" or self.config[dpid][domain_name]['mode'] == "InlineIDS"):
            if(prefix._version != 4):
              header = {"dl_type": 34525,
                        "phys_port": int(ports['wan'][0]['port_id'])}
            else:
              header = {"nw_dst":      int(prefix),
                        "nw_dst_mask": int(prefix.prefixlen),
                        "phys_port":   int(ports['wan'][0]['port_id'])}
          else:
            if(prefix._version != 4):
              header = {"dl_type": 34525,
                        "phys_port": int(in_port['port_id'])}
            else:
              header = {"nw_dst": int(prefix),
                        "nw_dst_mask": int(prefix.prefixlen),
                        "phys_port": int(in_port['port_id'])}

          actions = []
          #output to sensor (basically this is the IDS balance case)
          for sensor in sensors:
            actions.append({"type": "output",
                            "port": sensors[sensor]['port_id']})
            if(self.config[dpid][domain_name]['mode'] == "SciDMZ" or self.config[dpid][domain_name]['mode'] == "InlineIDS"):
                #append the FW or other destination
                if(ports.has_key('fw_wan') and len(ports['fw_wan']) > 0):
                  actions.append({"type": "output",
                                  "port": ports['fw_wan'][0]['port_id']})
                else:
                  actions.append({"type": "output",
                                  "port": in_port['port_id']})
            self.logger.debug("Header: %s" % str(header))
            self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                                    domain       = domain_name,
                                                    header       = header,
                                                    actions      = actions,
                                                    command      = "ADD",
                                                    idle_timeout = 0,
                                                    hard_timeout = 0,
                                                    priority     = 500)

  def delPrefix(self, dpid=None, domain_name=None, group_id=None, prefix=None):
    self.logger.debug("Remove Prefix")

    in_port  = None
    out_port = None
    fw_lan   = None
    fw_wan   = None

    #need to figure out the lan and wan ports
    ports = self.config[dpid][domain_name]['ports']
    for port in ports['lan']:
      for prefix_obj in port['prefixes']:
        if(prefix_obj['prefix'].Contains( prefix )):
          in_port = port

          header = {}
          if(prefix._version != 4):
            header = {"dl_type": 34525,
                      "phys_port": int(in_port['port_id'])}
          else:
            header = {"nw_src":      int(prefix),
                      "nw_src_mask": int(prefix.prefixlen),
                      "phys_port":   int(in_port['port_id'])}
    
          actions = []
          self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                                  domain       = domain_name,
                                                  header       = header,
                                                  actions      = actions,
                                                  command      = "DELETE_STRICT",
                                                  idle_timeout = 0,
                                                  hard_timeout = 0,
                                                  priority     = 500)
          header = {}
          if(self.config[dpid][domain_name]['mode'] == "SciDMZ" or self.config[dpid][domain_name]['mode'] == "InlineIDS"):
            header = {}
            if(prefix._version != 4):
              header = {"dl_type": 34525,
                        "phys_port": int(ports['wan'][0]['port_id'])}
            else:
              header = {"nw_dst":      int(prefix),
                        "nw_dst_mask": int(prefix.prefixlen),
                        "phys_port":   int(ports['wan'][0]['port_id'])}
          else:
            header = {"nw_dst":      int(prefix),
                      "nw_dst_mask": int(prefix.prefixlen),
                      "phys_port":   int(in_port['port_id'])}

            actions = []
            self.fireForwardingStateChangeHandlers( dpid         = dpid,
                                                    domain       = domain_name,
                                                    header       = header,
                                                    actions      = actions,
                                                    command      = "DELETE_STRICT",
                                                    idle_timeout = 0,
                                                    hard_timeout = 0,
                                                    priority     = 500)
    
  def movePrefix(self, dpid = None, domain_name=None, new_group_id=None, old_group_id=None, prefix=None):
    self.logger.debug("move prefix")
    #delete and add the prefix
    self.delPrefix(dpid, domain_name, old_group_id, prefix)
    self.addPrefix(dpid, domain_name, new_group_id, prefix)

  def remove_flow(self, ev):
    self.logger.debug("remove flow")
    
  def port_status(self, ev):
    self.logger.debug("port status handler")

  def port_stats(self, ev):
    self.logger.debug("port stats handler")

  def fireForwardingStateChangeHandlers( self,
                                         domain       = None,
                                         dpid         = None,
                                         header       = None,
                                         actions      = None,
                                         command      = None,
                                         idle_timeout = 0,
                                         hard_timeout = 0,
                                         priority     = 1):
    
    self.logger.debug("fireing forwarding state change handlers")
    self.logger.debug("Header: " + str(header))
    self.logger.debug("Actions: " + str(actions))
    self.logger.debug("Idle Timeout: " + str(idle_timeout))
    self.logger.debug("Hard Timeout: " + str(hard_timeout))
    self.logger.debug("Priority: " + str(priority))
    now = time.time()

    if(command == "ADD"):
      self.config[dpid][domain]['flows'].append({'dpid': dpid,
                                                 'header': header,
                                                 'actions': actions,
                                                 'priority': priority
                                                 })

    if(command == "DELETE" or command == "DELETE_STRICT"):
      for flow in self.config[dpid][domain]['flows']:
        if(flow['header'] == header and flow['priority'] == priority):
          self.config[dpid][domain]['flows'].remove(flow)

    if(idle_timeout):
      timeout = now + int(idle_timeout) 
      self.idleTimeouts.append({'timeout': timeout,
                                'dpid': dpid,
                                'domain': domain,
                                'idle_timeout': int(idle_timeout),
                                'pkt_count': 0,
                                'header': header,
                                'actions': actions,
                                'priority': priority,
                                'command': command})
    if(hard_timeout):
      timeout = now + int(hard_timeout)
      self.hardTimeouts.append({'timeout': timeout,
                                'dpid': dpid,
                                'domain': domain,
                                'header': header,
                                'actions': actions,
                                'priority': priority,
                                'command': command})

    for handler in self.switchForwardingChangeHandlers:
      handler( dpid = dpid,
               header = header,
               actions = actions,
               command = command,
               idle_timeout = idle_timeout,
               hard_timeout = hard_timeout,
               priority = priority)

  def updatePrefixBW(self,dpid, prefix, tx, rx):
    self.logger.debug("updating prefix bw")
    for domain_name in self.config[dpid]:
      for port in self.config[dpid][domain_name]['ports']['lan']:
        for pref in port['prefixes']:
          if(pref['prefix'].Contains( prefix )):
            self.logger.debug("Updating prefix " + str(prefix) + " bandwidth for %s %s", dpid, domain_name)
            self.config[dpid][domain_name]['balancer'].setPrefixBW(prefix, tx, rx)
            return

  def getSensorLoad(self, sensor):
    self.logger.debug("getting sensor load for sensor %s", sensor)
    for dpid in self.config:
      for domain in self.config['dpid']:
        if(self.config[dpid][domain]['balancer'].getSensorStatus(sensor) != -1):
          return self.config[dpid][domain]['balancer'].getSensorStatus(sensor)

  def setSensorLoad(self, sensor, load):
    self.logger.debug("updating sensor %s with load %d", sensor, load)
    for dpid in self.config:
      for domain in self.config['dpid']:
        if(self.config[dpid][domain]['balancer'].getSensorStatus(sensor) != -1):
          self.config[dpid][domain]['balancer'].setSensorStatus(sensor,load)
          return {success: 1}
    return {success: 0, msg: "Unable to find sensor with id: " + sensor}

  def getSwitchFlows(self, dpid=None):
    flows = []
    if(self.config.has_key(dpid)):
      for domain in self.config[dpid]:
        flows.extend(self.config[dpid][domain]['flows'])
    return flows

  def getDomainFlows(self, dpid=None, domain=None):
    if(self.config.has_key(dpid)):
      if(self.config[dpid].has_key(domain)):
        return self.config[dpid][domain]['flows']

  def getSwitchDomains(self, dpid=None):
    domains = []
    if(self.config.has_key(dpid)):
      for domain in self.config[dpid]:
        domains.append(domain)
    return domains

  def getSensorStatus(self, dpid=None, domain=None, sensor_id=None):
    if(self.config.has_key(dpid)):
      if(self.config[dpid].has_key(domain)):
        bal = self.config[dpid][domain]['balancer']
        return bal.getSensorStatus(sensor_id)

  def getDomainSensors(self, dpid=None, domain=None):
    if(self.config.has_key(dpid)):
      if(self.config[dpid].has_key(domain)):
        bal = self.config[dpid][domain]['balancer']
        sensor_groups = bal.getSensorGroups()
        return sensor_groups

  def getSwitches(self):
    switches = []
    for switch in self.switches:
      ports = []
      for port in switch.ports:
        port = switch.ports[port]        
        ports.append({'port_no': port.port_no,
                      'mac_addr': port.hw_addr,
                      'name': port.name,
                      'config': port.config,
                      'state': port.state,
                      'curr': port.curr,
                      'advertised': port.advertised,
                      'supported': port.supported,
                      'peer': port.peer
                      })
      switches.append({'dpid': "%016x" % switch.id,
                       'ports': ports,
                       'address': switch.address[0],
                       'is_active': switch.is_active
                       })
    return switches

  def get_domain_sensors(self, dpid=None, domain=None):
    if(dpid == None or domain == None):
      return
    return self.config[dpid][domain]['balancer'].getSensors()

  def run_balancers(self):
    for dpid in self.config:
      for domain_name in self.config[dpid]:
        self.logger.debug("Balancing: %s %s", dpid, domain_name)
        self.config[dpid][domain_name]['balancer'].balance()
        
  def getBalancer(self, dpid, domain_name):
    return self.config[dpid][domain_name]['balancer']

  

  def TimeoutFlows(self, dpid, flows):
    self.logger.debug("Looking for flows to timeout")
    now = time.time()
    for flow in self.hardTimeouts:
      if(flow['dpid'] == dpid):
        if(flow['timeout'] <= now):
          self.logger.info("Timing out flow due to Hard Timeout")
          #remove the flow
          self.fireForwardingStateChangeHandlers( dpid         = flow['dpid'],
                                                  domain       = flow['domain'],
                                                  header       = flow['header'],
                                                  actions      = flow['actions'],
                                                  command      = "DELETE_STRICT",
                                                  priority     = flow['priority'])
        
        self.hardTimeouts.remove(flow)

    #need to improve this! its a O(n^2)
    for flow in flows:
      for idle in self.idleTimeouts:
        if(dpid == idle['dpid']):
          #need to compare the flow match to the header
          #self.logger.error(str(flow['match']))
          #self.logger.error(str(idle['header']))
          if(cmp(flow['match'], idle['header']) == 0):
            #compare the dicts and they are the same
            #so update the flow count and the expires time
            if(idle['pkt_count'] == flow['packet_count']):
              #hasn't been updated since last time...
              self.logger.debug("Flow has not been updated")
            else:
              self.logger.debug("Flow has been updated")
              idle['timeout'] = time.time() + idle['idle_timeout']
              self.logger.debug("New Timeout: " + str(idle['timeout']))
              idle['pkt_count'] = flow['packet_count']
    
    for flow in self.idleTimeouts:
      if(flow['dpid'] == dpid):
        self.logger.debug("Flows current timeout: " + str(flow['timeout']) + " now " + str(now))
        if(flow['timeout'] <= now):
          self.logger.info("removing the flow due to idle timeout")
          #remove the flow
          self.fireForwardingStateChangeHandlers( dpid         = flow['dpid'],
                                                  domain       = flow['domain'],
                                                  header       = flow['header'],
                                                  actions      = flow['actions'],
                                                  command      = "DELETE_STRICT",
                                                  priority     = flow['priority'])
          self.idleTimeouts.remove(flow)
