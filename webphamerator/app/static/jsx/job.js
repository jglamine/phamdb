var humanDate = function(date) {
  if (date === null) {
    return 'unknown';
  }
  if (date.isAfter(moment().subtract(1, "days"))) {
    return date.fromNow();
  }
  return date.format('LLL');
};

var humanTimeDelta = function(duration) {
  if (duration === null) {
    return 'unknown';
  }
  var hours = pad(Math.round(duration.hours()), 2);
  var minutes = pad(Math.round(duration.minutes()), 2);
  var seconds = pad(Math.round(duration.seconds()), 2);

  return hours + ':' + minutes + ':' + seconds;

};

var pad = function(number, size) {
  var numberText = "" + number;
  if (numberText.length > size) {
    return numberText;
  }

  var s = "000000000" + numberText;
  return s.substr(s.length - size);
};

var Timer = React.createClass({
  getInitialState: function() {
    return {
      duration: moment.duration(moment().diff(this.props.start)),
      intervalId: null
    }
  },
  componentWillMount: function() {
    var ctx = this
    var intervalId = window.setInterval(function() {
      ctx.setState({
        duration: moment.duration(moment().diff(ctx.props.start)),
        intervalId: intervalId
      });
    }, 1000);
  },
  componentWillUnmount: function() {
    window.clearInterval(this.state.intervalId);
  },
  render: function() {
    return (
      <span>{humanTimeDelta(this.state.duration)}</span>
    );
  }
});

var JobStatus = React.createClass({
  getInitialState: function() {
    return this.readStatusFromJSON(window.reactInitialState);
  },
  readStatusFromJSON: function(data) {
    return {
      statusCode: data.statusCode,
      statusMessage: data.statusMessage,
      startTime: data.startTime ? moment(data.startTime) : null,
      endTime: data.endTime ? moment(data.endTime) : null,
      elapsedTime: data.elapsedTime ? moment.duration(data.elapsedTime, 'milliseconds') : null
    };
  },
  componentWillMount: function() {
    if (this.state.statusCode === 'queued' || this.state.statusCode === 'running') {
      window.setTimeout(this.refresh, 5000);
    }
  },
  refresh: function() {
    var ctx = this;
    $.getJSON('/api/jobs/' + this.props.jobId)
      .done(function(data) {
        var status = ctx.readStatusFromJSON(data);
        // redirect on job completion
        if (status.statusCode === 'success') {
          // set job as seen
          $.post('/api/jobs/' + ctx.props.jobId)
            .always(function() {
              window.location.replace(data.databaseUrl);
            });
        }
        ctx.setState(status);

        if (data.statusCode === 'running' || data.statusCode === 'queued' ) {
          window.setTimeout(ctx.refresh, 5000);
        }

      })
      .fail(function() {
        window.setTimeout(ctx.refresh, 5000);
      });
  },
  render: function() {
    var spinner = null;
    if (this.state.statusCode === 'loading') {
       spinner = <span className="glyphicon glyphicon-refresh spinning"></span>;
    }

    var times = null;
    if (this.state.statusCode === 'success' || this.state.statusCode === 'failed') {
      times = (
        <div>
          <p className="lead">
            Run time: {humanTimeDelta(this.state.elapsedTime)}
          </p>
          <p>
            Started: {humanDate(this.state.startTime)}
          </p>
          <p>
            Ended: {humanDate(this.state.endTime)}
          </p>
        </div>
      );
    }
    if (this.state.statusCode === 'queued') {
      times = (
        <div>
          <p>
            Added: {humanDate(this.state.startTime)}
          </p>
        </div>
      );
    }
    if (this.state.statusCode === 'running') {
      times = (
        <div>
          <p className="lead">
            Run time: <Timer start={this.state.startTime} />
          </p>
          <p>
            Started: {humanDate(this.state.startTime)}
          </p>
        </div>
      );
    }

    return (
      <div className="row">
        <div className="col-xs-9">
          <h2>{this.state.statusCode} <small>{this.state.statusMessage}</small> {spinner}</h2>
          {times}
          <p>
            Add {this.props.addCount} phages, remove {this.props.removeCount} phages.
          </p>
        </div>
        <div className="col-xs-3">
          <DeleteJobButton
          statusCode={this.state.statusCode}/>
        </div>
      </div>
    );
  }
});

var DeleteJobButton = React.createClass({
  render: function() {
    var disabled = false;
    if (this.props.statusCode === 'queued' || this.props.statusCode === 'running') {
      disabled = true;
    }
    return (
      <form method="post">
        <input type="hidden" name="delete" value="true"></input>
        <button type="submit" className="btn btn-danger"
          disabled={disabled}>
            Delete job
        </button>
      </form>
    );
  }
});

React.render(
  <JobStatus
   addCount={window.reactInitialState.addCount}
   removeCount={window.reactInitialState.removeCount}
   jobId={window.reactInitialState.jobId}/>,
  document.getElementById('react-content')
);