import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';
import Button from '@material-ui/core/Button';
import Slider from '@material-ui/lab/Slider';
import Grid from '@material-ui/core/Grid';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import Select from '@material-ui/core/Select';
import Checkbox from '@material-ui/core/Checkbox';
import Typography from '@material-ui/core/Typography';
import Tooltip from '@material-ui/core/Tooltip'
import { withSnackbar } from 'notistack';

import ProjectService from '../services/ProjectService'

const styles = theme => ({
    image : {
        maxWidth: '100px',
        maxHeight: '100px'
      }
});


class Configurator extends Component {
    constructor(props) {
        super(props)
        this.state = {
            parameters: props.parameters,
            values: props.values,
            parameterHelp: props.parameterHelp
        }
    }

    componentWillReceiveProps(nextProps) {
        this.setState({
            parameters: nextProps.parameters,
            values: nextProps.values,
            parameterHelp: nextProps.parameterHelp
        })
    }

    handleParameterChange = (value, parameter) => {
        let newState = Object.assign({}, this.state);    //creating copy of object
        newState.values[parameter] = value;
        this.setState(newState);
        this.props.onChange(parameter, value)
    };

    domCreateParameterDropdown = (parameters, values, parameterName) => {
        let items = parameters[parameterName].map((option, idx) => {
            return (
                <MenuItem key={idx} value={option}>{option}</MenuItem>
            )
        })
        return <React.Fragment>

            <Grid item sm={7} xs={10}>
                <InputLabel htmlFor={parameterName} />
                <Select
                    value={values[parameterName]}
                    fullWidth={true}
                    onChange={(e, val) => this.handleParameterChange(val.props.value, parameterName)}
                    inputProps={{
                        name: parameterName,
                        id: parameterName,
                    }}>
                    {items}
                </Select>
            </Grid>
            <Grid item sm={2} xs={2}>
            </Grid>
        </React.Fragment>
    }

    domCreateParameterSlider = (parameters, values, parameterName) => {
        return <React.Fragment>
            <Grid item sm={7} xs={10}>
                <Slider 
                    id={parameterName} 
                    value={values[parameterName]} 
                    min={parameters[parameterName][1]} 
                    max={parameters[parameterName][2]} 
                    step={parameters[parameterName][3]} 
                    onChange={(e, val) => this.handleParameterChange(val, parameterName)} />
            </Grid>
            <Grid item sm={2} xs={2}>
            <Typography>
                {values[parameterName] !== null ? values[parameterName].toFixed(Math.abs(Math.log10(parameters[parameterName][3]))) : null}
            </Typography>
            </Grid>
        </React.Fragment>
    }

    domCreateParameterCheckbox = (parameters, values, parameterName) => {
        return <React.Fragment>
            <Grid container sm={7} xs={10} justify="flex-end">
                <Checkbox
                    checked={values[parameterName]}
                    onChange={(e, val) => this.handleParameterChange(val, parameterName)}
                    value={parameterName}
                    color="primary"
                />
            </Grid>
            <Grid item sm={2} xs={2}>
            <Typography>
                {values[parameterName]}
            </Typography>
            </Grid>
        </React.Fragment>
    }

    handleGifUpload = async (event, parameterName) => {
        await ProjectService.uploadProjectAsset(event).then( res => this.handleParameterChange(res['filename'], parameterName)).catch(err => {
            console.error("Error uploading asset:", err);
            this.props.enqueueSnackbar("Error uploading asset. Check console for details.", { variant: 'error' })
        })
    }

    domCreateParameterGif = (parameters, values, parameterName) => {
        return <React.Fragment>
            <Grid container sm={7} xs={10} justify="flex-end">
                <img src={"project/assets/" + values[parameterName]} role="presentation" style={{maxWidht: '100px', maxHeight: '100px'}} />
            </Grid>
            <Grid item sm={2} xs={2}>
            <Typography>
            <input type="file" id="gif-input" onChange={(e) => this.handleGifUpload(e, parameterName)} style={{ display: 'none' }} />
                  <label htmlFor="gif-input">
                  
                  <Button component="span" variant="contained" size="small">
                  Upload
                      
                    </Button>                    
                  </label>
            </Typography>
            </Grid>
        </React.Fragment>
    }

    domCreateConfigList = (parameters, values, parameterHelp) => {
        if (parameters) {
            return Object.keys(parameters).map((data, index) => {
                let control;
                try {
                    if (parameters[data] instanceof Array) {
                        if (parameters[data].length >= 2 && parameters[data][0] == 'gif') {
                            control = this.domCreateParameterGif(parameters, values, data);
                        }
                        else if (parameters[data].length == 4 && !parameters[data].some(isNaN)) {
                            // Array of numbers -> Slider
                            control = this.domCreateParameterSlider(parameters, values, data);
                        }
                        else if (parameters[data].some(isNaN)) {
                            // Array of non-numbers -> DropDown
                            control = this.domCreateParameterDropdown(parameters, values, data);
                        } 
                    } else if (typeof (parameters[data]) === "boolean") {
                        // Simple boolean -> Checkbox
                        control = this.domCreateParameterCheckbox(parameters, values, data);
                    }
                } catch (error) {
                    console.error("Cannot create configurator entry for "+data, error)
                }
                if (control) {
                    var helpText = (parameterHelp != null && data in parameterHelp) ? parameterHelp[data] : "";
                    return (
                        <Tooltip title={helpText}>
                        <Grid key={index} container spacing={24}   alignItems="center" justify="center">
                            <Grid item sm={3} xs={12} >
                            <Typography>
                                {data}:
                            </Typography>
                            </Grid>
                            {control}
                        </Grid>
                        </Tooltip>
                    )
                } else {
                    console.error("undefined control for data", parameters[data])
                    return null
                }
            });
        }
    }

    render() {
        const { classes } = this.props;
        return (
            <div>
                {this.domCreateConfigList(this.state.parameters, this.state.values, this.state.parameterHelp)}
            </div>
        )
    }
}

Configurator.propTypes = {
    classes: PropTypes.object.isRequired,
    // parameters: PropTypes.object,
    // parameterHelp: PropTypes.object,
    // values: PropTypes.object,
    onChange: PropTypes.func
};

export default withSnackbar(withStyles(styles)(Configurator));