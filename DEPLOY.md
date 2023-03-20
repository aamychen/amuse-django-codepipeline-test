# Deploying

* Go to [Circle CI Workflows](https://circleci.com/gh/amuseio/workflows/amuse-django/tree/master) for `master` branch.

* Find commit checksum you want to deploy and enter the workflow.

* Click the **approve** step for the deploy job you want to execute.


## Pipeline

### Test

Test is run first and on all branches. No build, or release can happen without a successful test.


### Build

For every commit on master, a container build based on the commit hash will be uploaded to AWS ECR.
This happens in Circle CI using a [Circle CI Workflow](https://circleci.com/gh/amuseio/workflows/amuse-django/tree/master).


### Release

The container can be used as a basis for a AWS ECS Task Definition Revision. The Task Definition contains information
on how to launch a container and is always versioned forward. The Task Definition is the authoritative source for
*what* is running; Container version, Environment, and Configuration.

In order to create a Task Definition Circle CI finds all parameters in SSM Parameter Store for a special path and uses them as environment for the containers in the task definition. From this Circle CI will create Task Definition revisions.

Once task definition is created, Circle CI can automatically update the services to use the latest Task Defintion.

ECS in configured to only replace working containers if new ones manages to start and pass health check.

While containers are transitioning between versions different versions of the the code will run at the same time. Code changes should be integrated in the code base in such a way that this can happen safely. Only way to prevent this is with downtime and hands on work in ECS.


### Rollback

Different kinds of rollback processes should be applied given the nature of the incident. After a rollback has taken place, bad Task Definitions should be de-registered.


#### Normal Priority Rollback

Revert broken commit, merge, build and deploy.

This ensures code always goes forward and minimizes accidental redeploy of offending code, but takes the longest time. Be aware that the new deploy may use other env vars if they were updated in SSM.


#### High Priority Rollback

Find known good version of a deploy from master in Circle CI and rerun release job. This ensures task revisions always goes forward. Be aware that the new deploy may use other env vars if they were updated in SSM.


#### Panic Priority Rollback

Go to AWS ECS and update the `amuse-platform` service task definition to a known working release. This is the fastest way to roll back. Be aware that this also rolls back environmental variables.
