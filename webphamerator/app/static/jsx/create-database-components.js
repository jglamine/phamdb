function humanReadableFilesize(bytes) {
    var thresh = 1024;
    if(bytes < thresh) return bytes + ' B';
    var units = ['kB','MB','GB','TB','PB','EB','ZB','YB'];
    var u = -1;
    do {
        bytes /= thresh;
        ++u;
    } while(bytes >= thresh);
    return bytes.toFixed(1)+' '+units[u];
};

var DatabaseNameField = React.createClass({
  handleChange: function(event) {
    this.props.onUserInput(this.refs.nameInput.getDOMNode().value);
  },
  render: function() {
    var cs = React.addons.classSet;
    var classes = cs({
      'form-group': true,
      'has-feedback': true,
      'has-success': this.props.isNameValid && !this.props.disabled,
      'has-error': this.props.isNameValid === false
    });
    var feedbackIcon = null;
    if (this.props.isNameValid && !this.props.disabled) {
      feedbackIcon = (<span className="glyphicon glyphicon-ok form-control-feedback"></span>);
    }
    if (this.props.isNameValid === false) {
      feedbackIcon = (<span className="glyphicon glyphicon-remove form-control-feedback"></span>);
    }
    return (
      <div className={classes}>
        <label htmlFor="name">Database Name</label>
        <input type="text" className="form-control"
          placeholder="Enter a name for the database"
          ref="nameInput"
          id="name"
          value={this.props.name}
          disabled={this.props.disabled}
          onChange={this.handleChange} >
        </input>
        {feedbackIcon}
      </div>
    );
  }
});

var DatabaseDescriptionField = React.createClass({
  handleChange: function() {
    this.props.onUserInput(this.refs.descriptionInput.getDOMNode().value);
  },
  render: function() {
    return (
      <div className="form-group">
        <label htmlFor="description">Description</label>
        <textarea className="form-control"
          placeholder="Enter a description"
          ref="descriptionInput"
          id="description"
          value={this.props.description}
          onChange={this.handleChange} >
        </textarea>
      </div>
    );
  }
});

var DatabaseCddCheckbox = React.createClass({
  handleChange: function() {
    this.props.onUserInput(!this.props.checked)
  },
  render: function() {
    return (
      <div className="checkbox">
        <label htmlFor="cddCheckbox">
          <input type="checkbox"
            id="cddCheckbox"
            checked={this.props.checked}
            disabled={this.props.disabled}
            onChange={this.handleChange}>
          </input>
          Search Conserved Domain Database
        </label>
        <p className="help-block">Search for each gene in <a href="http://www.ncbi.nlm.nih.gov/Structure/cdd/cdd.shtml">NCBI’s conserved domain database</a>. This will significantly increase runtime.</p>
      </div>
    );
  }
});

var PhageDeleteList = React.createClass({
  render: function() {
    var phages = [];
    var index = 0;
    var ctx = this;
    this.props.phages.forEach(function(phage) {
      phages.push(<SelectablePhage
                   name={phage.name}
                   phage_id={phage.id}
                   genes={phage.genes}
                   selected={phage.selected}
                   index={index}
                   setSelected={ctx.props.setSelected} />);
      index += 1;
    });

    return (
      <div>
        <h2>Current Phages</h2>
        <p>
          Uncheck a phage to remove it from the database.
        </p>
        <div className="phage-list list-group">{phages}</div>
      </div>
    );
  }
});

var SelectablePhage = React.createClass({
  handleCheckbox: function() {
    this.props.setSelected(this.props.index, !this.props.selected);
  },
  render: function() {
    var database = '';
    if (this.props.database !== undefined) {
      database = ', database: ' + this.props.database;
    }

    if (this.props.genes === 1) {
      var genesText = 'gene';
    } else {
      var genesText = 'genes';
    }

    return (
      <li className="list-group-item checkbox container-fluid">
        <div className="row">
            <div className="col-xs-12">
              <label>
                <input type="checkbox"
                  checked={this.props.selected}
                  onChange={this.handleCheckbox}>
                </input>
                <strong>{this.props.name}</strong>  <small>(id: {this.props.phage_id}{database}, {this.props.genes} {genesText})</small>
              </label>
            </div>
        </div>
      </li>
    );
  }
});

var ImportPhageForm = React.createClass({
  render: function() {
    var phages = [];
    var index = 0;
    var ctx = this;
    this.props.phages.forEach(function(phage) {
      phages.push(<SelectablePhage
                   name={phage.name}
                   phage_id={phage.id}
                   genes={phage.genes}
                   database={phage.databaseName}
                   selected={phage.selected}
                   index={index}
                   setSelected={ctx.props.onSelectPhage} />);
      index += 1;
    });

    return (
      <div>
        <h2>Import Phages from Database</h2>
        <p>
          Select a phage to import it from a database.
        </p>

        <FilteredDatabaseList
          selectedPhages={this.props.phages}
          databaseId={this.props.databaseId}
          onAddPhage={this.props.onAddPhage}
          onRemovePhage={this.props.onRemovePhage} />

        <div className="phage-list list-group">{phages}</div>
      </div>
    );
  }
});

var FilteredDatabaseList = React.createClass({
  getInitialState: function() {
    return {
      databases: [],
      phages: [],
      loaded: false,
      phagesLoading: false
    };
  },
  componentDidMount: function() {
    var ctx = this;
    $.getJSON('/api/database')
    .done(function(data) {
      var databases = _.filter(data.databases, function(item) {
        return item.id !== ctx.props.databaseId;
      }).map(function(item, index) {
        item.selected = index === 0;
        return item;
      });

      ctx.setState({
        databases: databases,
        loaded: true,
        phages: [],
        phagesLoading: true
      }, ctx.loadPhages);
    })
    .fail(function(response) {
      ctx.setState({
        loaded: null,
        phagesLoading: false
      });
    });
  },
  loadPhages: function() {
    if (this.state.databases.length === 0) {
      this.setState({
        phagesLoading: false
      });
      return;
    }

    database = _.find(this.state.databases, function(item) {
      return item.selected === true;
    });

    var ctx = this;
    $.getJSON('/api/database/' + database.id + '/phages')
    .done(function(data) {
      var phages = _.forEach(data.phages, function(item) {
        var selectedIndex = _.findIndex(ctx.props.selectedPhages, function(selectedItem) {
          return selectedItem.database === database.id && item.id === selectedItem.id;
        });
        item.selected = selectedIndex !== -1;
        item.database = database.id;
        item.databaseName = database.name;
        return item;
      });
      ctx.setState({
        phages: phages,
        phagesLoading: false
      });
    })
    .fail(function() {
      ctx.setState({
        phages: [],
        phagesLoading: false
      });
    })
    
  },
  selectDatabase: function(index) {
    var databases = this.state.databases.slice();
    _.each(databases, function(database, i) {
      database.selected = i === index;
    });
    this.setState({
      databases: databases,
      phages: [],
      phagesLoading: true
    }, this.loadPhages);
  },
  phageSelected: function(index, selected) {
    if (selected === true) {
      this.props.onAddPhage(this.state.phages[index]);
    } else if (selected === false) {
      this.props.onRemovePhage(this.state.phages[index]);
    }
    var phages = this.state.phages.slice();
    phages[index].selected = selected;
    this.setState({
      phages: phages
    });
  },
  render: function() {
    return (
      <div className="container-fluid">
        <div className="row">
          <div className="col-xs-6">
            <h4>Databases</h4>
            <DatabaseList
              databases={this.state.databases}
              loaded={this.state.loaded}
              onSelectDatabase={this.selectDatabase} />
          </div>
          <div className="col-xs-6">
            <h4>Phages</h4>
            <DatabasePhageList
              phages={this.state.phages}
              loading={this.state.phagesLoading}
              setSelected={this.phageSelected} />
          </div>
        </div>
      </div>
    );
  }
});

var DatabasePhageList = React.createClass({
  render: function() {
    var phages = [];
    var index = 0;
    var ctx = this;
    this.props.phages.forEach(function(phage) {
      phages.push(<DatabasePhageListItem
                   name={phage.name}
                   phage_id={phage.id}
                   selected={phage.selected}
                   genes={phage.genes}
                   index={index}
                   setSelected={ctx.props.setSelected} />);
      index += 1;
    });

    if (this.props.loading) {
      return (
        <span className="glyphicon glyphicon-refresh spinning"></span>
      );
    }

    return (
      <div className="list-group list-scroll">{phages}</div>
    );
  }
});

var DatabasePhageListItem = React.createClass({
  handleClick: function(event) {
    event.preventDefault();
    this.props.setSelected(this.props.index, !this.props.selected);
  },
  render: function() {
    var cs = React.addons.classSet;
    var classes = cs({
      'list-group-item': true,
      'database-list-item': true,
      'active': this.props.selected,
      'container-fluid': true
    });

    if (this.props.genes === 1) {
      var genesText = 'gene';
    } else {
      var genesText = 'genes';
    }

    return (
      <a className={classes}
        onClick={this.handleClick}>
        <strong>{this.props.name}</strong>  <small>(id: {this.props.phage_id}, {this.props.genes} {genesText})</small>
      </a>
    );
  }
});

var DatabaseList = React.createClass({
  render: function() {
    var databases = [];
    var index = 0;
    var ctx = this;
    this.props.databases.forEach(function(database) {
      databases.push(<SelectableDatabase
                   name={database.name}
                   phages={database.phages}
                   selected={database.selected}
                   index={index}
                   setSelected={ctx.props.onSelectDatabase} />);
      index += 1;
    });

    if (this.props.loaded === false) {
      return (
        <span className="glyphicon glyphicon-refresh spinning"></span>
      );
    }
    if (this.props.loaded === null) {
      return (
        <div>
          <p>Error loading database list. Refresh the page to try again.
          </p>
        </div>
      );
    }
    if (this.props.databases.length === 0) {
      return (
        <div>
          <p>No databases found.</p>
        </div>
      );
    }

    return (
      <div className="list-group list-scroll">{databases}</div>
    );
  }
});

var SelectableDatabase = React.createClass({
  clicked: function(event) {
    event.preventDefault();
    this.props.setSelected(this.props.index);
  },
  render: function() {
    var cs = React.addons.classSet;
    var classes = cs({
      'list-group-item': true,
      'database-list-item': true,
      'active': this.props.selected
    });

    var phagesText = this.props.phages + " ";
    if (this.props.phages === 1) {
      phagesText += "phage";
    } else {
      phagesText += "phages";
    }

    return (
      <a className={classes}
        onClick={this.clicked}>
        <strong>{this.props.name}</strong> <small>{phagesText}</small>
      </a>
    );
  }
});

var PhageUploadButton = React.createClass({
  handleFiles: function() {
    var files = this.refs.fileInput.getDOMNode().files;
    if (files.length) {
      this.props.handleFiles(files, this.resetFileInput);
    }
  },
  resetFileInput: function() {
    var input = this.refs.fileInput.getDOMNode();
    input.value = '';
    if (input.value) {
      input.type = "text";
      input.type = "file";
    }
  },
  render: function() {
    return (
      <div className="form-group">
        <input type="file" className="btn" id="genbankFileInput"
          multiple
          ref="fileInput"
          accept=".gb,.txt,.gbk"
          onChange={this.handleFiles}>
        </input>
        <p className="help-block">Select genbank files or drag and drop.</p>
      </div>
    );
  }
});

var LoadingBar = React.createClass({
  render: function() {
    var progressStyle = {
      width: "" + this.props.progress * 100 + "%"
    };

    return (
      <div className="progress">
        <div className="progress-bar" role="progressbar"
          style={progressStyle}></div>
      </div>
    );
  }
});

var PhageFile = React.createClass({
  handleCheckbox: function() {
    this.props.setState(this.props.index, {
      selected: !this.props.selected
    });
  },
  render: function() {
    var filename = this.props.file.name;
    var size = humanReadableFilesize(this.props.file.size);
    var hasError = this.props.errors.length !== 0;
    var checked = this.props.selected && !hasError;
    var loading = this.props.progress !== 1;

    var loadedInformation = null;
    if (!loading) {
      if (hasError) {
        loadedInformation = (
          <span>
            {this.props.errors.length}
            {this.props.errors.length === 1 ? " error" : " errors"}
          </span>
        );
      } else {
        loadedInformation = (
        <span>
          {"name:"} <strong>{this.props.phage_name}</strong>
          {" id:"} <strong>{this.props.phage_id}</strong>
          {" genes:"} <strong>{this.props.gene_count}</strong>
        </span>
        );
      }
    }

    var errorMessages = null;
    if (hasError) {
      var errorRows = [];
      _.each(_.sortBy(this.props.errors, 'line'), function(error) {
        errorRows.push(
          <div className="row">
            <div className="col-xs-2 col-md-1">
              <strong>line {error.line}</strong>
            </div>
            <div className="col-xs-10 col-md-11">
              {error.message}
            </div>
          </div>
          );
      });

      errorMessages = (
        <div>
          <hr className="error"></hr>
          {errorRows}
        </div>
      );
    }

    var listItemClasses = React.addons.classSet({
      'list-group-item': true,
      'checkbox': true,
      'container-fluid': true,
      'list-group-item-danger': hasError
    });

    return (
      <li className={listItemClasses}>
        <div className="row">
            <div className="col-xs-6 col-sm-4 col-md-4">
              <label>
                <input type="checkbox"
                  checked={checked}
                  disabled={hasError}
                  onChange={this.handleCheckbox}>
                </input>
                <strong>{filename}</strong> <small>({size})</small>
              </label>
            </div>
            <div className="hidden-xs col-sm-3 col-md-4">
              <LoadingBar progress={this.props.progress} />
            </div>
            <div className="col-xs-6 col-sm-5 col-md-4">
              {loadedInformation}
            </div>
        </div>
        {errorMessages}
      </li>
    );
  }
});

var PhageFileList = React.createClass({
  render: function() {
    var items = [];
    var index = 0;
    var ctx = this;
    this.props.files.forEach(function(file) {
      items.push(<PhageFile
                  file={file.file}
                  file_id={file.file_id}
                  progress={file.progress}
                  selected={file.selected}
                  phage_id={file.phage_id}
                  phage_name={file.phage_name}
                  gene_count={file.gene_count}
                  errors={file.errors}
                  index={index}
                  setState={ctx.props.setFileState} />);
      index += 1;
    });
    return (
      <div className="phage-list list-group">{items}</div>
    );
  }
});

var PhageUploadForm = React.createClass({
  render: function() {
    return (
      <div>
        <h2>Upload Genbank Files</h2>
        <PhageUploadButton handleFiles={this.props.handleFiles} />
        <PhageFileList
          files={this.props.files}
          setFileState={this.props.setFileState}/>
      </div>
    );
  }
});

var CreateDatabaseFormSummary = React.createClass({
  render: function() {
    var uploadCount = 0;
    _.each(this.props.files, function(file) {
      if (file.selected && file.errors.length === 0) {
        uploadCount += 1;
      }
    });

    _.each(this.props.importPhages, function(item) {
      if (item.selected) {
        uploadCount += 1;
      }
    });

    var deleteCount = 0;
    _.each(this.props.phages, function(phage) {
      if (phage.selected === false) {
        deleteCount += 1;
      }
    });

    return (
      <div>
        <h2>Summary</h2>
        <p>Add {uploadCount} {uploadCount === 1 ? "phage" : "phages"}</p>
        <p>Delete {deleteCount} {deleteCount === 1 ? "phage" : "phages"}</p>
      </div>
    );
  }
});

var CreateDatabaseButton = React.createClass({
  render: function() {
    var readyToSubmit = this.props.isNameValid && this.props.uploadSlots;

    return (
      <div>
        <button type="button" className="btn btn-primary btn-large btn-block"
           disabled={!readyToSubmit}
           onClick={this.props.handleClick}>
          {this.props.text}
        </button>
        <LoadingModal />
      </div>
    );
  }
});

var LoadingModal = React.createClass({
  render: function() {

    return (
      <div className="modal fade" id="loadingModal" tabindex="-1" role="dialog">
        <div className="modal-dialog">
          <div className="modal-content">
            <div className="modal-header">
              <h4 className="modal-title">Submitting Job <span className="glyphicon glyphicon-refresh spinning"></span></h4>
            </div>
            <div className="modal-body">
              <div className="container-fluid">
                <div className="row">
                  <div className="col-xs-12">
                    <p>
                      Submitting job and checking for conflicts. This may take a few seconds.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
});

var SubmissionErrors = React.createClass({
  render: function() {

    var cs = React.addons.classSet;
    var classes = cs({
      'alert': true,
      'alert-danger': true,
      'hidden': this.props.errorMessages.length === 0
    });

    var errors = [];
    _.each(this.props.errorMessages, function(error) {
      errors.push(
        <div>{error}</div>
      );
    });

    return (
      <div className={classes} role="alert">
        <strong>Error submitting job</strong>
        {errors}
      </div>
    );
  }
});

var CreateDatabaseForm = React.createClass({
  // when databaseId is not null, it indicates that we are editing rather
  // than creating a database.
  getInitialState: function() {
    var state = {
      name: '',
      isNameValid: null,
      description: '',
      cddSearch: false,
      phages: [],
      importPhages: [],
      files: [],
      uploadSlots: 1,
      handleUploadsComplete: null,
      submissionErrors: [],
      databaseId: null
    };

    if (window.reactInitialState) {
      state = _.assign(state, window.reactInitialState);
      _.each(state.phages, function(phage) {
        phage.selected = true;
      });
    }

    return state;
  },
  validateDatabaseName: function(nameText) {
    if (nameText.length === 0) {
      return;
    }

    if (nameText.trim().length === 0) {
      this.setState({
        isNameValid: false
      });
      return;
    }

    var ctx = this;
    $.get('/api/database-name-taken', {name: nameText})
      .done(function() {
        ctx.setState({
          isNameValid: true
        });
      })
      .fail(function(data) {
        if (data.status === 409) {
          ctx.setState({
            isNameValid: false
          });
        }
      });
  },
  handleNameInput: function(nameText) {
    this.setState({
      name: nameText,
      isNameValid: null
    });

    this.validateDatabaseName(nameText);
  },
  handleDescriptionInput: function(descriptionText) {
    this.setState({
      description: descriptionText
    });
  },
  handleFiles: function(fileList, callback) {
    var newFiles = [];
    _.each(fileList, function(file) {
      newFiles.push({
        file: file,
        file_id: null,
        progress: 0.0,
        selected: true,
        phage_id: null,
        gene_count: null,
        errors: []
      });
    });

    var files = this.state.files.slice();
    files.unshift.apply(files, newFiles);

    this.setState({
      files: files,
      handleUploadsComplete: callback
    }, this.uploadNextFile);

  },
  uploadNextFile: function() {
    var ctx = this;

    var findIndexOfFileHandle = function(fileHandle) {
      return _.findIndex(ctx.state.files, function(state) {
        return state.file === fileHandle;
      });
    }

    if (this.state.uploadSlots) {
      var index = _.findLastIndex(this.state.files, function(file) {
        return file.progress === 0.0;
      });
      if (index === -1) {
        if (ctx.state.handleUploadsComplete) {
          ctx.state.handleUploadsComplete();
        }
        return;
      }
      this.setState({
        uploadSlots: 0
      });

      var fileHandle = this.state.files[index].file;

      var handleProgress = function(event) {
        if (event.lengthComputable) {
          var progress = event.loaded / event.total;
          var index = findIndexOfFileHandle(fileHandle);
          if (index !== -1) {
            ctx.setFileState(index, {
              progress: progress
            });
          }
        }
      };

      var formData = new FormData();
      formData.append('file', fileHandle, fileHandle.name);

      $.ajax({
          url: '/api/genbankfiles',
          type: 'POST',
          xhr: function() {
              var myXhr = $.ajaxSettings.xhr();
              if(myXhr.upload){
                  myXhr.upload.addEventListener('progress', handleProgress, false);
              }
              return myXhr;
          },
          data: formData,
          cache: false,
          contentType: false,
          processData: false,
          dataType: 'json'
      })
        .done(function(data) {
          var index = findIndexOfFileHandle(fileHandle);
          ctx.setFileState(index, {
            progress: 1.0,
            file_id: data.phage.file_id,
            phage_id: data.phage.phage_id,
            phage_name: data.phage.name,
            gene_count: data.phage.number_of_genes 
          });
        })
        .fail(function(response) {
          var errors = ['Error communicating with server.'];
          var index = findIndexOfFileHandle(fileHandle);
          if (response.status === 400) {
            var data = $.parseJSON(response.responseText);
            errors = data.errors;
          }
          ctx.setFileState(index, {
            errors: errors,
            progress: 1.0,
          });
        })
        .always(function() {
          ctx.setState({
            uploadSlots: 1
          }, ctx.uploadNextFile);
        });
    }
  },
  setFileState: function(index, changeset) {
    var files = this.state.files.slice();
    _.assign(files[index], changeset);
    this.setState({
      files: files
    });
  },
  setPhageSelected: function(index, selected) {
    var phages = this.state.phages.slice();
    phages[index].selected = selected;
    this.setState({
      phages: phages
    });
  },
  handleCddInput: function(checked) {
    this.setState({
      cddSearch: checked
    });
  },
  addImportPhage: function(phage) {
    var importPhages = this.state.importPhages.slice();
    phage = _.clone(phage);
    phage.selected = true;
    importPhages.push(phage);
    this.setState({
      importPhages: importPhages
    });
  },
  removeImportPhage: function(phage) {
    var importPhages = this.state.importPhages.slice();
    _.remove(importPhages, function(p) {
      return p.id === phage.id && p.database === phage.database;
    });
    this.setState({
      importPhages: importPhages
    });
  },
  setImportPhageSelected: function(index, selected) {
    var importPhages = this.state.importPhages.slice();
    importPhages[index].selected = selected;
    this.setState({
      importPhages: importPhages
    });
  },
  handleSubmit: function() {
    var ctx = this;

    this.setState({
      submissionErrors: []
    });

    $('#loadingModal').modal({
      keyboard: false,
      backdrop: "static"
    });

    var file_ids = _.filter(this.state.files, function(file) {
      return file.selected === true && file.file_id !== null;
    })
    .map(function(file) {
      return file.file_id;
    });

    var phage_ids_to_delete = _.filter(this.state.phages, function(phage) {
      return phage.selected === false;
    })
    .map(function(phage) {
      return phage.id;
    });

    var phages_from_other_databases = _.filter(this.state.importPhages, function(phage) {
      return phage.selected === true;
    })
    .map(function(phage) {
      return {
        id: phage.id,
        database: phage.database
      };
    });

    var data = {
        name: this.state.name,
        description: this.state.description,
        cdd_search: this.state.cddSearch,
        file_ids: file_ids,
        phages_to_delete: phage_ids_to_delete,
        phages_from_other_databases: phages_from_other_databases
      };

    var apiUrl = '/api/databases';
    if (this.state.databaseId !== null) {
      apiUrl = '/api/database/' + this.state.databaseId;
    }

    $.ajax({
      url: apiUrl,
      type: 'post',
      dataType: 'json',
      contentType: 'application/json',
      processData: false,
      data: JSON.stringify(data)
    })
    .done(function(data) {
      window.location.href = '/jobs/' + data.job_id;
    })
    .fail(function(data) {
      var errorMessages = null;
      if (data.status === 400) {
        var jsonData = $.parseJSON(data.responseText);
        errorMessages = jsonData.errors;
      } else if (data.status === 412) {
        errorMessages = [data.responseText];
      } else if (data.status === 500) {
        errorMessages = ['An unknown error occurred on the server. Please try again.'];
      } else {
        errorMessages = ['Error communicating with the server. Please try again.'];
      }

      ctx.setState({
        submissionErrors: errorMessages
      });
      $('#loadingModal').modal('hide');
    });
  },
  componentWillMount: function() {
    this.validateDatabaseName = _.debounce(this.validateDatabaseName, 800);
  },
  render: function() {
    var submitButtonText = "Create Database";
    if (this.state.databaseId !== null) {
      submitButtonText = "Submit";
    }

    var phages = null;
    if (this.state.databaseId !== null) {
      phages = (
        <PhageDeleteList
          phages={this.state.phages}
          setSelected={this.setPhageSelected} />
      );
    }

    return (
      <div>
        <SubmissionErrors
          errorMessages={this.state.submissionErrors} />
        <DatabaseNameField
          name={this.state.name}
          isNameValid={this.state.isNameValid}
          onUserInput={this.handleNameInput}
          disabled={this.state.databaseId !== null} />
        <DatabaseDescriptionField
          description={this.state.description}
          onUserInput={this.handleDescriptionInput} />
        <DatabaseCddCheckbox
          checked={this.state.cddSearch}
          onUserInput={this.handleCddInput}
          disabled={this.state.databaseId !== null} />
        {phages}
        <ImportPhageForm
          phages={this.state.importPhages}
          databaseId={this.state.databaseId}
          onAddPhage={this.addImportPhage}
          onRemovePhage={this.removeImportPhage}
          onSelectPhage={this.setImportPhageSelected} />
        <PhageUploadForm
          files={this.state.files}
          handleFiles={this.handleFiles}
          setFileState={this.setFileState} />
        <CreateDatabaseFormSummary
          files={this.state.files}
          phages={this.state.phages}
          importPhages={this.state.importPhages} />
        <CreateDatabaseButton
          handleClick={this.handleSubmit}
          text={submitButtonText}
          isNameValid={this.state.isNameValid}
          uploadSlots={this.state.uploadSlots} />
      </div>
    );
  }
});

var SqlUploadForm = React.createClass({
  render: function() {
    return (
      <div>
        <h2>Upload SQL File</h2>
        <p>
          Import a database from a SQL dump.
        </p>
        <SqlUploadButton
          handleFile={this.props.handleFile} />
        <SqlFileWithUploadProgress
          file={this.props.file} />
      </div>
    );
  }
});

var SqlUploadForm = React.createClass({
  handleFile: function() {
    var files = this.refs.fileInput.getDOMNode().files;
    if (files.length) {
      this.props.handleFile(files[0], this.resetFileInput);
    }
  },
  resetFileInput: function() {
    var input = this.refs.fileInput.getDOMNode();
    input.value = '';
    if (input.value) {
      input.type = "text";
      input.type = "file";
    }
  },
  render: function() {
    return (
      <div className="form-group">
      <h2>Upload SQL File</h2>
        <input type="file" className="btn"
          ref="fileInput"
          accept=".sql"
          onChange={this.handleFile}>
        </input>
        <SqlFileWithUploadProgress file={this.props.file} />
      </div>
    );
  }
});

var SqlFileWithUploadProgress = React.createClass({
  render: function() {
    if (this.props.file === null) {
      return <p>No file selected.</p>;
    }
    return (
      <div>
        <strong>{this.props.file.name}</strong> <span>{humanReadableFilesize(this.props.file.size)}</span>
        <LoadingBar progress={this.props.file.progress} />
      </div>
    );
  }
});

var ImportDatabaseForm = React.createClass({
  getInitialState: function() {
    var state = {
      name: '',
      isNameValid: null,
      description: '',
      file: null,
      submissionErrors: []
    };

    return state;
  },
  validateDatabaseName: function(nameText) {
    if (nameText.length === 0) {
      return;
    }

    if (nameText.trim().length === 0) {
      this.setState({
        isNameValid: false
      });
      return;
    }

    var ctx = this;
    $.get('/api/database-name-taken', {name: nameText})
      .done(function() {
        ctx.setState({
          isNameValid: true
        });
      })
      .fail(function(data) {
        if (data.status === 409) {
          ctx.setState({
            isNameValid: false
          });
        }
      });
  },
  setFileProgress: function(progress) {
    var file = this.state.file;
    file.progress = progress;
    this.setState({
      file: file
    });
  },
  handleFile: function(file, callback) {
    var ctx = this;
    this.setState({
      file: file
    }, function() {
      var handleProgress = function(event) {
        if (event.lengthComputable) {
          var progress = event.loaded / event.total;
          ctx.setFileProgress(progress);
        }
      };

      var formData = new FormData();
      formData.append('file', file, file.name);

      $.ajax({
        url: '/api/file',
        type: 'POST',
        xhr: function() {
          var myXhr = $.ajaxSettings.xhr();
          if(myXhr.upload){
              myXhr.upload.addEventListener('progress', handleProgress, false);
          }
          return myXhr;
        },
        data: formData,
        cache: false,
        contentType: false,
        processData: false,
        dataType: 'json'
      })
      .done(function(data) {
        var file = ctx.state.file;
        file.id = data.id;
        ctx.setState({
          file: file
        });
        ctx.setFileProgress(1.0);
      })
      .fail(function(response) {
        ctx.setState({
          file: null,
          submissionErrors: ['Failed to upload file "' + file.name + '".']
        });
      })
      .always(callback);
    });
  },
  handleNameInput: function(nameText) {
    this.setState({
      name: nameText,
      isNameValid: null
    });

    this.validateDatabaseName(nameText);
  },
  handleDescriptionInput: function(descriptionText) {
    this.setState({
      description: descriptionText
    });
  },
  handleSubmit: function() {
    var ctx = this;

    this.setState({
      submissionErrors: []
    });

    $('#loadingModal').modal({
      keyboard: false,
      backdrop: "static"
    });

    var data = {
        name: this.state.name,
        description: this.state.description,
        cdd_search: false,
        sql_dump_id: this.state.file.id
      };

    $.ajax({
      url: '/api/databases',
      type: 'post',
      dataType: 'json',
      contentType: 'application/json',
      processData: false,
      data: JSON.stringify(data)
    })
    .done(function(data) {
      window.location.href = '/databases/' + data.database_id;
    })
    .fail(function(data) {
      var errorMessages = null;
      if (data.status === 400) {
        var jsonData = $.parseJSON(data.responseText);
        errorMessages = jsonData.errors;
      } else if (data.status === 412) {
        errorMessages = [data.responseText];
      } else if (data.status === 500) {
        errorMessages = ['An unknown error occurred on the server. Please try again.'];
      } else {
        errorMessages = ['Error communicating with the server. Please try again.'];
      }

      ctx.setState({
        submissionErrors: errorMessages
      });
      $('#loadingModal').modal('hide');
    });
  },
  componentWillMount: function() {
    this.validateDatabaseName = _.debounce(this.validateDatabaseName, 800);
  },
  render: function() {
    var uploaded = false;
    if (this.state.file && this.state.file.id) {
      uploaded = true;
    }

    return (
      <div>
        <SubmissionErrors
          errorMessages={this.state.submissionErrors} />
        <DatabaseNameField
          name={this.state.name}
          isNameValid={this.state.isNameValid}
          onUserInput={this.handleNameInput}
          disabled={false} />
        <DatabaseDescriptionField
          description={this.state.description}
          onUserInput={this.handleDescriptionInput} />
        <SqlUploadForm
          file={this.state.file}
          handleFile={this.handleFile} />
        <CreateDatabaseButton
          handleClick={this.handleSubmit}
          text={"Submit"}
          isNameValid={this.state.isNameValid}
          uploadSlots={uploaded ? 1 : 0} />
      </div>
    );
  }
});
