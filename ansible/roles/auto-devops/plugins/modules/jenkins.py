#!/usr/bin/env python

# Copyright: (c) 2020, Yiğit Can Başalma <yigit.basalma@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule

import traceback
import jenkins

JENKINS = None
RESULT = dict(
    changed=False,
    error="",
    output=""
)
JOBS = [
    dict(name="0_Build", display_name="0-) Build", jenkinsfile="Jenkinsfile.build",
         description="Build image, test code, and push image to repository."),
    dict(name="0_BranchBuild", display_name="0-) Branch Build", jenkinsfile="Jenkinsfile.branchBuild",
         description="Build image, test code, and push image to repository."),
    dict(name="1_BranchDeploy", display_name="1-) Branch Deploy", jenkinsfile="Jenkinsfile.branchDeploy",
         description="Deploy image to required environment."),
    dict(name="{env_index}_Deploy_{environment}", display_name="{env_index}-) {environment} Deploy", jenkinsfile="Jenkinsfile.deploy",
         description="Deploy job into {environment} environment.")
]
JOB_XML = """<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job@1174.vdcb_d054cf74a_">
  <actions/>
  <description>{description}</description>
  <displayName>{display_name}</displayName>
  <keepDependencies>false</keepDependencies>
  <properties>
    <jenkins.model.BuildDiscarderProperty>
      <strategy class="hudson.tasks.LogRotator">
        <daysToKeep>5</daysToKeep>
        <numToKeep>10</numToKeep>
        <artifactDaysToKeep>-1</artifactDaysToKeep>
        <artifactNumToKeep>-1</artifactNumToKeep>
      </strategy>
    </jenkins.model.BuildDiscarderProperty>
  </properties>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps@2686.v7c37e0578401">
    <scm class="hudson.plugins.git.GitSCM" plugin="git@4.11.0">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>{jenkinsfile_repo}</url>
          <credentialsId>gitlab-deployuser-ssh</credentialsId>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/main</name>
        </hudson.plugins.git.BranchSpec>
      </branches>
      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      <submoduleCfg class="empty-list"/>
      <extensions/>
    </scm>
    <scriptPath>{jenkinsfile_location}</scriptPath>
    <lightweight>false</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>"""


def run(**kwargs):
    # Create folder
    folder = f"{kwargs['project']}/{kwargs['app_name']}".replace(" ", "")
    branch_folder = f"{folder}/Branch"
    JENKINS.create_folder(kwargs['project'].replace(" ", ""), ignore_failures=True)
    JENKINS.create_folder(folder, ignore_failures=True)
    JENKINS.create_folder(branch_folder, ignore_failures=True)

    environment = kwargs["environment"]
    env_index = len([
        s
        for i in JENKINS.get_jobs()
        if i["name"] == kwargs['project'].replace(" ", "")
        for e in i["jobs"]
        if e["name"] == kwargs['app_name'].replace(" ", "")
        for s in e["jobs"]
        if s["name"] not in ("Branch", )
    ])

    if not env_index:
        env_index = 1

    for job in JOBS:
        job_exists = False

        if environment not in ("test", ) and job["name"] in ("0_Build", "0_BranchBuild", "1_BranchDeploy"):
            continue

        if job["name"] not in ("0_Build", "0_BranchBuild", "1_BranchDeploy"):
            try:
                for i in range(env_index):
                    if JENKINS.job_exists(f"{folder}/{job['name'].format(env_index=i, environment=environment.title())}"):
                        job_exists = True

                if job_exists:
                    continue

                JENKINS.create_job(
                    f"{folder}/{job['name'].format(env_index=env_index, environment=environment.title())}",
                    JOB_XML.format(
                        display_name=job["display_name"].format(env_index=env_index, environment=environment.title()),
                        jenkinsfile_repo=kwargs["jenkinsfile_repo"],
                        jenkinsfile_location=f'{kwargs["jenkinsfile_location"]}/{job["jenkinsfile"]}',
                        description=job["description"].format(environment=environment.title())
                    )
                )
            except jenkins.JenkinsException:
                pass
            finally:
                if job["name"] not in ("0_BranchBuild", "1_BranchDeploy"):
                    env_index += 1
                continue

        try:
            JENKINS.create_job(
                f"{folder if job['name'] in ('0_Build', ) else branch_folder}/{job['name']}",
                JOB_XML.format(
                    display_name=job["display_name"],
                    jenkinsfile_repo=kwargs["jenkinsfile_repo"],
                    jenkinsfile_location=f'{kwargs["jenkinsfile_location"]}/{job["jenkinsfile"]}',
                    description=job["description"]
                )
            )
        except jenkins.JenkinsException:
            pass
        finally:
            if job["name"] not in ("0_Build", "0_BranchBuild", "1_BranchDeploy"):
                env_index += 1


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        url=dict(type="str", required=True),
        username=dict(type="str", required=True),
        password=dict(type="str", no_log=True),
        jenkinsfile_repo=dict(type="str", required=True),
        jenkinsfile_location=dict(type="str", required=True),
        jenkins_security=dict(type="bool", default=False),
        app_name=dict(type="str", required=True),
        project=dict(type="str", required=True),
        environment=dict(type="str", required=True)
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Vars
    extra_args = dict()

    global JENKINS

    if module.params["jenkins_security"]:
        extra_args = dict(username=module.params["username"], password=module.params["password"])

    JENKINS = jenkins.Jenkins(f'{module.params["url"]}', **extra_args)

    # noinspection PyBroadException
    try:
        run(**module.params)
    except Exception:
        RESULT["failed"] = True
        RESULT["error"] = traceback.format_exc()

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**RESULT)


def main():
    run_module()


if __name__ == "__main__":
    main()
